"""SMS API — send booking-bekræftelser og opfølgninger via Twilio."""

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.secretary_call import SecretaryCall
from app.models.ai_secretary import AiSecretary
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class SmsRequest(BaseModel):
    to: str
    message: str


class BookingConfirmRequest(BaseModel):
    call_id: UUID


class SmsResponse(BaseModel):
    success: bool
    message: str


@router.post("/send", response_model=SmsResponse)
async def send_sms(
    data: SmsRequest,
    user: User = Depends(get_current_user),
):
    """Send en fritekst-SMS til et telefonnummer."""
    from app.services.sms_service import send_sms as _send

    success = await asyncio.to_thread(_send, data.to, data.message)
    if not success:
        raise HTTPException(status_code=503, detail="SMS afsendelse fejlede — tjek Twilio credentials")
    return SmsResponse(success=True, message=f"SMS sendt til {data.to}")


@router.post("/booking-confirmation/{call_id}", response_model=SmsResponse)
async def send_booking_confirmation(
    call_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send en automatisk booking-bekræftelse baseret på et sekretær-opkald."""
    # Hent opkaldet
    call_result = await db.execute(
        select(SecretaryCall).where(SecretaryCall.id == call_id)
    )
    call = call_result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Opkald ikke fundet")

    if not call.caller_phone:
        raise HTTPException(status_code=400, detail="Opkaldet har intet telefonnummer registreret")

    # Hent sekretær-konfiguration for virksomhedsnavn
    sec_result = await db.execute(
        select(AiSecretary).where(AiSecretary.user_id == user.id)
    )
    secretary = sec_result.scalar_one_or_none()
    business_name = secretary.business_name if secretary else "Virksomheden"

    from app.services.sms_service import send_booking_confirmation as _send_confirm

    summary = call.summary or "Din henvendelse er modtaget."
    # Begræns summary til 80 tegn i SMS
    if len(summary) > 80:
        summary = summary[:77] + "..."

    success = await asyncio.to_thread(
        _send_confirm,
        call.caller_phone,
        call.caller_name or "",
        business_name,
        summary,
    )

    if not success:
        raise HTTPException(status_code=503, detail="SMS afsendelse fejlede")

    # Markér bekræftelse sendt
    from datetime import datetime, timezone
    call.confirmation_sent_at = datetime.now(timezone.utc)
    await db.commit()

    return SmsResponse(
        success=True,
        message=f"Bekræftelses-SMS sendt til {call.caller_phone}",
    )
