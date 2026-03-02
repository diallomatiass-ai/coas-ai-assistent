"""
Webhook-endpoints for AI Sekretær service-to-service integration.

Disse endpoints bruges af den standalone AI Sekretær Docker-service
til at hente konfiguration og poste opkaldsdata.

Auth: X-Secretary-Key header (delt hemmelighed, ikke JWT).
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.ai_secretary import AiSecretary
from app.models.secretary_call import SecretaryCall
from app.services.customer_matching import find_or_create_from_call, normalize_phone
from app.services.calendar_service import CalendarService, TimeSlot

logger = logging.getLogger(__name__)

router = APIRouter()
calendar_service = CalendarService()

# ── Urgency mapping (dansk → Ahmes) ────────────────────────────────────

URGENCY_MAP = {
    "lav": "low",
    "normal": "medium",
    "høj": "high",
    "akut": "high",
    # Pass-through for allerede engelske værdier
    "low": "low",
    "medium": "medium",
    "high": "high",
}


# ── Auth dependency ─────────────────────────────────────────────────────

async def verify_webhook_key(x_secretary_key: str = Header(...)):
    """Validér API-nøgle fra AI Sekretær servicen."""
    if not settings.secretary_webhook_key:
        raise HTTPException(status_code=500, detail="Webhook key not configured")
    if x_secretary_key != settings.secretary_webhook_key:
        raise HTTPException(status_code=401, detail="Invalid webhook key")


# ── Schemas ─────────────────────────────────────────────────────────────

class WebhookCallCreate(BaseModel):
    phone_number: str  # Twilio-nummeret (til opslag af secretary)
    caller_name: str | None = None
    caller_phone: str | None = None
    caller_address: str | None = None
    summary: str
    transcript: str | None = None
    urgency: str = "normal"
    call_type: str | None = None
    messages: list[dict] | None = None
    called_at: datetime | None = None


# ── GET /secretary-config ───────────────────────────────────────────────

@router.get("/secretary-config", dependencies=[Depends(verify_webhook_key)])
async def get_secretary_config(
    phone: str = Query(..., description="Twilio-nummeret der ringes til"),
    db: AsyncSession = Depends(get_db),
):
    """
    Hent AI Secretary konfiguration baseret på Twilio-telefonnummer.
    Bruges af AI Sekretær ved opkaldsstart til at hente system prompt, greeting, voice osv.
    """
    normalized = normalize_phone(phone)

    # Find aktiv secretary med matchende telefonnummer
    result = await db.execute(select(AiSecretary).where(AiSecretary.is_active == True))
    secretaries = result.scalars().all()

    secretary = None
    for s in secretaries:
        if s.phone_number and normalize_phone(s.phone_number) == normalized:
            secretary = s
            break

    if not secretary:
        raise HTTPException(status_code=404, detail="No active secretary for this number")

    # Hent primær kontaktperson
    contacts = secretary.contact_persons or []
    primary = contacts[0] if contacts else {}

    # Byg system prompt med kalender-instruktioner hvis booking er aktiveret
    system_prompt = secretary.system_prompt
    booking_enabled = bool(secretary.booking_rules and secretary.booking_rules.get("enabled"))

    if booking_enabled:
        calendar_instructions = (
            "\n\nKALENDERBOOKING:\n"
            f"Du har adgang til {secretary.business_name}s kalender og kan booke aftaler direkte.\n"
            "- Når kunden vil booke: Spørg om de har en foretrukken dag eller uge, og brug check_availability.\n"
            "- Præsentér 2-3 ledige tider naturligt: \"Jeg kan se der er ledig tid tirsdag klokken 9, "
            "eller onsdag klokken 13. Hvad passer dig bedst?\"\n"
            "- Brug KUN book_appointment EFTER kunden har bekræftet et specifikt tidspunkt.\n"
            "- Sig altid dato og tidspunkt tydeligt, og bekræft adressen.\n"
            "- Afslut med: \"Du får en SMS-bekræftelse med alle detaljer.\""
        )
        system_prompt += calendar_instructions

    return {
        "business_name": secretary.business_name,
        "greeting_text": secretary.greeting_text,
        "system_prompt": system_prompt,
        "voice_id": secretary.voice_id,
        "owner_phone": primary.get("phone", ""),
        "owner_name": primary.get("name", ""),
        "phone_number": secretary.phone_number,
        "confirmation_enabled": secretary.confirmation_enabled,
        "booking_enabled": booking_enabled,
        "booking_rules": secretary.booking_rules,
    }


# ── POST /secretary-call ────────────────────────────────────────────────

@router.post("/secretary-call", dependencies=[Depends(verify_webhook_key)], status_code=201)
async def create_secretary_call(
    data: WebhookCallCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Modtag opkaldsdata fra AI Sekretær efter afsluttet opkald.
    Opretter SecretaryCall, linker til kunde, trigger bekræftelse + action extraction.
    """
    normalized = normalize_phone(data.phone_number)

    # Find secretary via telefonnummer
    result = await db.execute(select(AiSecretary).where(AiSecretary.is_active == True))
    secretaries = result.scalars().all()

    secretary = None
    for s in secretaries:
        if s.phone_number and normalize_phone(s.phone_number) == normalized:
            secretary = s
            break

    if not secretary:
        raise HTTPException(status_code=404, detail="No secretary for this number")

    # Map urgency
    urgency = URGENCY_MAP.get(data.urgency, "medium")

    # Byg transcript fra messages hvis ikke leveret direkte
    transcript = data.transcript
    if not transcript and data.messages:
        lines = []
        for msg in data.messages:
            role = msg.get("role", "unknown")
            text = msg.get("text", "")
            if role == "customer":
                lines.append(f"Kunde: {text}")
            elif role == "assistant":
                lines.append(f"AI: {text}")
        transcript = "\n".join(lines)

    # Opret SecretaryCall
    call = SecretaryCall(
        secretary_id=secretary.id,
        caller_name=data.caller_name,
        caller_phone=data.caller_phone,
        caller_address=data.caller_address,
        summary=data.summary,
        transcript=transcript,
        urgency=urgency,
        called_at=data.called_at or datetime.now(timezone.utc),
    )
    db.add(call)
    await db.flush()

    # Auto-detect/opret kunde
    customer_linked = False
    try:
        customer = await find_or_create_from_call(
            data.caller_name, data.caller_phone, data.caller_address,
            secretary.user_id, db,
        )
        call.customer_id = customer.id
        customer_linked = True
    except Exception:
        logger.exception("Failed to link webhook call to customer")

    await db.commit()
    await db.refresh(call)

    # Auto-send SMS-bekræftelse hvis aktiveret og telefonnummer findes
    if secretary.confirmation_enabled and data.caller_phone:
        try:
            from app.services.sms_service import send_booking_confirmation
            import asyncio
            short_summary = (data.summary or "")[:80]
            asyncio.get_event_loop().run_until_complete(
                asyncio.to_thread(
                    send_booking_confirmation,
                    data.caller_phone,
                    data.caller_name or "",
                    secretary.business_name,
                    short_summary,
                )
            )
            call.confirmation_sent_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as exc:
            logger.warning("Auto-SMS bekræftelse fejlede: %s", exc)

    # Trigger bekræftelsesmail (asynkront)
    try:
        from app.tasks.worker import send_call_confirmation_task
        send_call_confirmation_task.delay(str(call.id))
    except Exception:
        logger.debug("Confirmation task not available yet")

    # Trigger action item extraction (asynkront)
    try:
        from app.tasks.worker import extract_action_items_task
        extract_action_items_task.delay(str(call.id))
    except Exception:
        logger.debug("Action extraction task not available yet")

    logger.info(f"Webhook call created: {call.id} for secretary {secretary.business_name}")

    return {
        "id": str(call.id),
        "secretary_id": str(call.secretary_id),
        "customer_id": str(call.customer_id) if call.customer_id else None,
        "status": "created",
        "customer_linked": customer_linked,
    }


# ── Helper: Find secretary + user via telefonnummer ────────────────────

async def _find_secretary_by_phone(phone: str, db: AsyncSession) -> AiSecretary | None:
    normalized = normalize_phone(phone)
    result = await db.execute(select(AiSecretary).where(AiSecretary.is_active == True))
    for s in result.scalars().all():
        if s.phone_number and normalize_phone(s.phone_number) == normalized:
            return s
    return None


# ── GET /calendar/availability — AI Sekretær tjekker kalender ──────────

class CalendarBookRequest(BaseModel):
    phone: str
    date: str          # YYYY-MM-DD
    time: str          # HH:MM
    customer_name: str
    customer_phone: str
    customer_address: str = ""
    description: str
    duration: int = 60


@router.get("/calendar/availability", dependencies=[Depends(verify_webhook_key)])
async def calendar_availability(
    phone: str = Query(..., description="Twilio-nummeret"),
    date_from: str = Query(..., description="Start-dato YYYY-MM-DD"),
    date_to: str = Query(..., description="Slut-dato YYYY-MM-DD"),
    preferred_time: str = Query("any", description="morning | afternoon | any"),
    db: AsyncSession = Depends(get_db),
):
    """
    AI Sekretæren kalder denne endpoint for at tjekke kalender-ledighed.
    Auth: X-Secretary-Key header.
    """
    secretary = await _find_secretary_by_phone(phone, db)
    if not secretary:
        raise HTTPException(status_code=404, detail="No secretary for this number")

    slots = await calendar_service.get_available_slots(
        user_id=str(secretary.user_id),
        date_from=date_from,
        date_to=date_to,
        preferred_time=preferred_time,
        db=db,
    )

    return {
        "slots": [
            {"date": s.date, "start_time": s.start_time, "end_time": s.end_time}
            for s in slots
        ]
    }


# ── POST /calendar/book — AI Sekretær booker aftale ────────────────────

@router.post("/calendar/book", dependencies=[Depends(verify_webhook_key)])
async def calendar_book(
    data: CalendarBookRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    AI Sekretæren kalder denne endpoint for at booke en aftale.
    Auth: X-Secretary-Key header.
    """
    secretary = await _find_secretary_by_phone(data.phone, db)
    if not secretary:
        raise HTTPException(status_code=404, detail="No secretary for this number")

    slot = TimeSlot(date=data.date, start_time=data.time, end_time="")
    customer_data = {
        "customer_name": data.customer_name,
        "customer_phone": data.customer_phone,
        "customer_address": data.customer_address,
    }

    result = await calendar_service.book_appointment(
        user_id=str(secretary.user_id),
        slot=slot,
        customer_data=customer_data,
        description=data.description,
        db=db,
        duration_minutes=data.duration,
    )

    return {
        "success": result.success,
        "event_id": result.event_id,
        "message": result.message,
    }
