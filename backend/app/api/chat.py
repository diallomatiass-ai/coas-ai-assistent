"""
AI Command Chat — naturligt sprog til alle funktioner.
Understøtter emails, kalender, opgaver, opkald, kunder og dagsoverblik.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.email_message import EmailMessage
from app.models.mail_account import MailAccount
from app.models.ai_suggestion import AiSuggestion
from app.models.action_item import ActionItem
from app.models.secretary_call import SecretaryCall
from app.models.calendar_event import CalendarEvent
from app.models.customer import Customer
from app.utils.auth import get_current_user
from app.models.user import User
from app.services.mail_gmail import send_reply
from app.services.ai_engine import generate_reply, _call_ollama_generate
from app.services.calendar_service import get_calendar_service

logger = logging.getLogger(__name__)
router = APIRouter()


class CommandRequest(BaseModel):
    message: str
    confirm: bool = False
    pending_action: dict | None = None


class CommandResponse(BaseModel):
    response: str
    actions_taken: list[str] = []
    requires_confirmation: bool = False
    pending_action: dict | None = None
    data: dict | None = None


# ---------------------------------------------------------------------------
# Kontekst-indsamling
# ---------------------------------------------------------------------------

async def _get_context(user: User, db: AsyncSession) -> dict:
    """Hent samlet kontekst fra alle funktioner til AI'en."""
    now = datetime.now(timezone.utc)

    # Emails
    accounts = (await db.execute(
        select(MailAccount).where(MailAccount.user_id == user.id)
    )).scalars().all()
    account_ids = [a.id for a in accounts]

    emails = []
    if account_ids:
        emails = (await db.execute(
            select(EmailMessage)
            .where(EmailMessage.account_id.in_(account_ids))
            .order_by(EmailMessage.received_at.desc())
            .limit(30)
        )).scalars().all()

    # Action items
    action_items = (await db.execute(
        select(ActionItem)
        .where(ActionItem.user_id == user.id, ActionItem.status != "done")
        .order_by(ActionItem.deadline.asc().nullslast())
        .limit(15)
    )).scalars().all()

    # Opkald
    calls = (await db.execute(
        select(SecretaryCall)
        .join(SecretaryCall.secretary)
        .where(SecretaryCall.secretary.has(user_id=user.id))
        .order_by(SecretaryCall.called_at.desc())
        .limit(10)
    )).scalars().all()

    # Kalender (kommende events)
    cal_events = (await db.execute(
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == user.id,
            CalendarEvent.start_time >= now,
        )
        .order_by(CalendarEvent.start_time.asc())
        .limit(10)
    )).scalars().all()

    # Kunder
    customers = (await db.execute(
        select(Customer)
        .where(Customer.user_id == user.id)
        .order_by(Customer.created_at.desc())
        .limit(20)
    )).scalars().all()

    return {
        "emails": emails,
        "action_items": action_items,
        "calls": calls,
        "cal_events": cal_events,
        "customers": customers,
        "accounts": accounts,
    }


def _build_context_summary(ctx: dict) -> str:
    """Byg kortfattet tekstuel kontekst til AI-prompten."""
    now = datetime.now(timezone.utc)
    lines = []

    # Emails
    emails = ctx["emails"]
    unread = [e for e in emails if not e.is_read]
    lines.append(f"EMAILS: {len(emails)} i alt, {len(unread)} ulæste")
    for e in emails[:8]:
        status = "ULÆST" if not e.is_read else "læst"
        lines.append(f"  email:{str(e.id)[:8]} [{e.category or '?'}][{e.urgency or '?'}][{status}] '{e.subject or '?'}' fra {e.from_address}")

    # Action items
    lines.append(f"\nOPGAVER (aktive): {len(ctx['action_items'])} stk")
    for a in ctx["action_items"]:
        deadline_str = a.deadline.strftime("%d/%m kl.%H:%M") if a.deadline else "ingen deadline"
        overdue = " [OVERSKREDET]" if a.deadline and a.deadline < now else ""
        lines.append(f"  opgave:{str(a.id)[:8]} [{a.status}] '{a.action}: {a.description or ''}' deadline:{deadline_str}{overdue}")

    # Opkald
    lines.append(f"\nOPKALD: {len(ctx['calls'])} seneste")
    for c in ctx["calls"][:6]:
        lines.append(f"  opkald:{str(c.id)[:8]} [{c.status}][{c.urgency}] '{c.caller_name or 'Ukendt'}' - {c.summary[:60] if c.summary else ''}")

    # Kalender
    lines.append(f"\nKALENDER (kommende): {len(ctx['cal_events'])} events")
    for ev in ctx["cal_events"][:6]:
        lines.append(f"  event:{str(ev.id)[:8]} '{ev.title}' {ev.start_time.strftime('%d/%m kl.%H:%M')}")

    # Kunder
    lines.append(f"\nKUNDER: {len(ctx['customers'])} stk")
    for cust in ctx["customers"][:8]:
        lines.append(f"  kunde:{str(cust.id)[:8]} '{cust.name}' [{cust.status}] tlf:{cust.phone or '-'}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Intent parsing
# ---------------------------------------------------------------------------

async def _parse_intent(message: str, context_summary: str) -> dict:
    """Brug Ollama til at fortolke brugerens hensigt. Returnerer struktureret JSON."""
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")

    prompt = f"""Du er AI-assistent for en dansk virksomhed. Analyser kommandoen og returner KUN valid JSON.

DATO/TID NU: {now_str} UTC (dansk tid = UTC+1, dvs. tilføj 1 time)

TILGÆNGELIGE HANDLINGER:
Emails: search, summary, suggest, mark_read, generate_reply, delete, send
Kalender: create_calendar_event, list_calendar
Opgaver: create_action_item, complete_action_item, list_action_items
Opkald: update_call_status, list_calls
Kunder: get_customer
Overblik: daily_brief
Samtale: chat

KONTEKST:
{context_summary}

BRUGERENS KOMMANDO: "{message}"

Returner JSON i dette format (udelad ikke felter, brug null for ubrugte):
{{
  "action": "en af handlingerne ovenfor",
  "description": "hvad du forstår kommandoen som",
  "filters": {{
    "category": null,
    "is_read": null,
    "from_address": null,
    "search_text": null,
    "urgency": null
  }},
  "reply_instructions": null,
  "send_to": null,
  "send_subject": null,
  "send_body": null,
  "calendar_title": null,
  "calendar_start": null,
  "calendar_end": null,
  "calendar_description": null,
  "action_type": null,
  "action_description": null,
  "action_deadline": null,
  "action_item_id": null,
  "call_id": null,
  "call_status": null,
  "call_notes": null,
  "customer_name": null,
  "status_filter": null
}}

REGLER FOR DATOER: Beregn ISO8601 dato ud fra DATO/TID NU.
- "i morgen kl 14" = {(datetime.now(timezone.utc) + timedelta(days=1)).strftime('%Y-%m-%d')}T13:00:00Z
- "på fredag" = næste fredag kl 09:00
- "næste uge" = mandag i næste uge kl 09:00
- Kalenderevents varer 1 time medmindre andet er angivet

Svar KUN med JSON, ingen forklaringer."""

    try:
        raw = await _call_ollama_generate(prompt)
        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        logger.warning("Intent parsing fejlede: %s", e)
        return {"action": "chat", "description": "Kunne ikke fortolke kommandoen", "filters": {}}


# ---------------------------------------------------------------------------
# Email helpers (fra original)
# ---------------------------------------------------------------------------

def _filter_emails(filters: dict, emails: list) -> list:
    results = emails
    if filters.get("category"):
        results = [e for e in results if e.category == filters["category"]]
    if filters.get("is_read") is not None:
        results = [e for e in results if e.is_read == filters["is_read"]]
    if filters.get("from_address"):
        term = filters["from_address"].lower()
        results = [e for e in results if term in (e.from_address or "").lower()]
    if filters.get("search_text"):
        term = filters["search_text"].lower()
        results = [e for e in results if
                   term in (e.subject or "").lower() or
                   term in (e.body_text or "").lower() or
                   term in (e.from_address or "").lower()]
    if filters.get("urgency"):
        results = [e for e in results if e.urgency == filters["urgency"]]
    return results


# ---------------------------------------------------------------------------
# Hoved-endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=CommandResponse)
async def command(
    req: CommandRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ctx = await _get_context(user, db)
    emails = ctx["emails"]
    action_items = ctx["action_items"]
    calls = ctx["calls"]
    cal_events = ctx["cal_events"]
    now = datetime.now(timezone.utc)

    # -----------------------------------------------------------------------
    # Bekræftelse af afventende handling
    # -----------------------------------------------------------------------
    if req.confirm and req.pending_action:
        action = req.pending_action.get("action")

        if action == "delete":
            email_ids = req.pending_action.get("email_ids", [])
            await db.execute(sql_delete(AiSuggestion).where(
                AiSuggestion.email_id.in_([uuid.UUID(i) for i in email_ids])
            ))
            await db.execute(sql_delete(EmailMessage).where(
                EmailMessage.id.in_([uuid.UUID(i) for i in email_ids])
            ))
            await db.commit()
            return CommandResponse(
                response=f"Slettede {len(email_ids)} email(s).",
                actions_taken=[f"Slettede {len(email_ids)} emails"]
            )

        if action == "send":
            send_data = req.pending_action.get("send_data", {})
            account = ctx["accounts"][0] if ctx["accounts"] else None
            if not account:
                return CommandResponse(response="Ingen aktiv mailkonto. Forbind Gmail under Indstillinger.")
            success = await send_reply(
                account=account, db=db,
                to=send_data.get("to", ""),
                subject=send_data.get("subject", ""),
                body=send_data.get("body", ""),
            )
            if success:
                return CommandResponse(response=f"Email sendt til {send_data.get('to')}.", actions_taken=["Email sendt"])
            return CommandResponse(response="Afsendelse mislykkedes.")

        if action == "create_calendar_event":
            ev_data = req.pending_action.get("event_data", {})
            try:
                start = datetime.fromisoformat(ev_data["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(ev_data["end_time"].replace("Z", "+00:00"))
            except Exception:
                return CommandResponse(response="Kunne ikke fortolke dato/tid. Prøv igen med et præcist tidspunkt.")

            cal_event = CalendarEvent(
                user_id=user.id,
                title=ev_data["title"],
                description=ev_data.get("description"),
                start_time=start,
                end_time=end,
                event_type="manual",
            )
            db.add(cal_event)
            await db.commit()
            await db.refresh(cal_event)

            # Sync til ekstern kalender
            account = ctx["accounts"][0] if ctx["accounts"] else None
            if account:
                try:
                    svc = get_calendar_service(account, db)
                    ext_id = await svc.create_event(cal_event)
                    if ext_id:
                        cal_event.external_event_id = ext_id
                        cal_event.provider = account.provider
                        cal_event.account_id = account.id
                        await db.commit()
                except Exception:
                    pass

            synced = " (synkroniseret til kalender)" if cal_event.external_event_id else ""
            return CommandResponse(
                response=f"Aftale oprettet{synced}:\n📅 **{cal_event.title}**\n🕐 {start.strftime('%d/%m/%Y kl. %H:%M')} – {end.strftime('%H:%M')}",
                actions_taken=[f"Kalenderaftale oprettet: {cal_event.title}"]
            )

        if action == "complete_action_item":
            item_id = req.pending_action.get("item_id")
            if item_id:
                result = await db.execute(
                    select(ActionItem).where(ActionItem.id == uuid.UUID(item_id), ActionItem.user_id == user.id)
                )
                item = result.scalar_one_or_none()
                if item:
                    item.status = "done"
                    await db.commit()
                    return CommandResponse(
                        response=f"Opgaven '{item.action}' er markeret som færdig.",
                        actions_taken=[f"Opgave afsluttet: {item.action}"]
                    )
            return CommandResponse(response="Kunne ikke finde opgaven.")

        if action == "update_call_status":
            call_id = req.pending_action.get("call_id")
            new_status = req.pending_action.get("status")
            notes = req.pending_action.get("notes")
            if call_id:
                result = await db.execute(select(SecretaryCall).where(SecretaryCall.id == uuid.UUID(call_id)))
                call = result.scalar_one_or_none()
                if call:
                    call.status = new_status or call.status
                    if notes:
                        call.notes = notes
                    await db.commit()
                    return CommandResponse(
                        response=f"Opkald fra {call.caller_name or 'ukendt'} opdateret til '{call.status}'.",
                        actions_taken=[f"Opkald opdateret: {call.status}"]
                    )
            return CommandResponse(response="Kunne ikke finde opkaldet.")

    # -----------------------------------------------------------------------
    # Ny kommando: byg kontekst og fortolk intent
    # -----------------------------------------------------------------------
    context_summary = _build_context_summary(ctx)
    intent = await _parse_intent(req.message, context_summary)
    action = intent.get("action", "chat")
    filters = intent.get("filters") or {}

    # -----------------------------------------------------------------------
    # DAILY BRIEF — samlet dagsoverblik
    # -----------------------------------------------------------------------
    if action == "daily_brief":
        today_events = [ev for ev in ctx["cal_events"] if
                        ev.start_time.date() == now.date()]
        unread_emails = [e for e in emails if not e.is_read]
        high_emails = [e for e in emails if e.urgency == "high" and not e.is_read]
        overdue_items = [a for a in action_items if a.deadline and a.deadline < now]
        pending_items = [a for a in action_items if a.status == "pending" and (not a.deadline or a.deadline >= now)]
        new_calls = [c for c in calls if c.status == "new"]

        lines = [f"**Dagsoverblik — {now.strftime('%A %d. %B').capitalize()}**\n"]

        if today_events:
            lines.append(f"📅 **Dagens aftaler ({len(today_events)}):**")
            for ev in today_events:
                lines.append(f"  • {ev.start_time.strftime('%H:%M')} {ev.title}")

        if overdue_items:
            lines.append(f"\n🔴 **Overskredet ({len(overdue_items)}):**")
            for a in overdue_items[:3]:
                lines.append(f"  • {a.action}: {a.description or ''}")

        if high_emails:
            lines.append(f"\n⚡ **Hasteemails ulæst ({len(high_emails)}):**")
            for e in high_emails[:3]:
                lines.append(f"  • '{e.subject or '?'}' fra {e.from_address}")

        if new_calls:
            lines.append(f"\n📞 **Nye opkald ({len(new_calls)}):**")
            for c in new_calls[:3]:
                lines.append(f"  • {c.caller_name or 'Ukendt'} — {c.summary[:50] if c.summary else ''}")

        if pending_items:
            lines.append(f"\n📋 **Kommende opgaver ({len(pending_items)}):**")
            for a in pending_items[:3]:
                dl = a.deadline.strftime("(deadline %d/%m)") if a.deadline else ""
                lines.append(f"  • {a.action}: {a.description or ''} {dl}")

        if not any([today_events, overdue_items, high_emails, new_calls, pending_items]):
            lines.append("Alt er i orden — ingen aktive opgaver eller hasteemails. ✅")

        lines.append(f"\n📊 {len(unread_emails)} ulæste emails · {len(action_items)} aktive opgaver · {len(ctx['cal_events'])} kommende aftaler")

        return CommandResponse(
            response="\n".join(lines),
            data={
                "today_events": len(today_events),
                "unread": len(unread_emails),
                "overdue": len(overdue_items),
                "new_calls": len(new_calls),
            }
        )

    # -----------------------------------------------------------------------
    # LIST CALENDAR
    # -----------------------------------------------------------------------
    if action == "list_calendar":
        if not ctx["cal_events"]:
            return CommandResponse(response="Ingen kommende kalenderaftaler.")
        lines = [f"**Kommende aftaler ({len(ctx['cal_events'])}):**\n"]
        for ev in ctx["cal_events"][:8]:
            icon = {"action_item": "📋", "call": "📞"}.get(ev.event_type, "📅")
            lines.append(f"{icon} **{ev.start_time.strftime('%d/%m kl. %H:%M')}** — {ev.title}")
            if ev.description:
                lines.append(f"   _{ev.description[:60]}_")
        return CommandResponse(response="\n".join(lines))

    # -----------------------------------------------------------------------
    # CREATE CALENDAR EVENT
    # -----------------------------------------------------------------------
    if action == "create_calendar_event":
        title = intent.get("calendar_title")
        start_raw = intent.get("calendar_start")
        end_raw = intent.get("calendar_end")

        if not title or not start_raw:
            return CommandResponse(response="Angiv titel og tidspunkt. Eksempel: \"Book møde med Henrik tirsdag kl. 10\"")

        try:
            start = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            if not end_raw:
                end = start + timedelta(hours=1)
            else:
                end = datetime.fromisoformat(str(end_raw).replace("Z", "+00:00"))
        except Exception:
            return CommandResponse(response="Kunne ikke fortolke dato/tid. Prøv med format: \"tirsdag kl. 10\"")

        desc = intent.get("calendar_description")
        preview = f"📅 **{title}**\n🕐 {start.strftime('%d/%m/%Y kl. %H:%M')} – {end.strftime('%H:%M')}"
        if desc:
            preview += f"\n📝 {desc}"

        return CommandResponse(
            response=f"Skal jeg oprette denne aftale?\n\n{preview}",
            requires_confirmation=True,
            pending_action={
                "action": "create_calendar_event",
                "event_data": {
                    "title": title,
                    "start_time": start.isoformat(),
                    "end_time": end.isoformat(),
                    "description": desc,
                }
            }
        )

    # -----------------------------------------------------------------------
    # CREATE ACTION ITEM
    # -----------------------------------------------------------------------
    if action == "create_action_item":
        action_type = intent.get("action_type") or "følg_op"
        desc = intent.get("action_description") or req.message
        deadline_raw = intent.get("action_deadline")

        deadline = None
        if deadline_raw:
            try:
                deadline = datetime.fromisoformat(str(deadline_raw).replace("Z", "+00:00"))
            except Exception:
                pass

        item = ActionItem(
            user_id=user.id,
            action=action_type,
            description=desc,
            status="pending",
            deadline=deadline,
        )
        db.add(item)
        await db.commit()

        dl_str = f" (deadline {deadline.strftime('%d/%m kl. %H:%M')})" if deadline else ""
        return CommandResponse(
            response=f"Opgave oprettet: **{action_type}** — {desc}{dl_str}",
            actions_taken=[f"Opgave oprettet: {action_type}"]
        )

    # -----------------------------------------------------------------------
    # LIST ACTION ITEMS
    # -----------------------------------------------------------------------
    if action == "list_action_items":
        status_filter = intent.get("status_filter")
        items = action_items
        if status_filter:
            items = [a for a in items if a.status == status_filter]

        overdue = [a for a in items if a.deadline and a.deadline < now]
        upcoming = [a for a in items if not (a.deadline and a.deadline < now)]

        lines = [f"**Opgaver ({len(items)} aktive):**\n"]
        if overdue:
            lines.append(f"🔴 **Overskredet ({len(overdue)}):**")
            for a in overdue:
                lines.append(f"  • {a.action}: {a.description or ''} — {a.deadline.strftime('%d/%m') if a.deadline else ''}")
        if upcoming:
            lines.append(f"\n📋 **Kommende ({len(upcoming)}):**")
            for a in upcoming[:6]:
                dl = a.deadline.strftime("(%d/%m)") if a.deadline else "(ingen deadline)"
                lines.append(f"  • {a.action}: {a.description or ''} {dl}")

        return CommandResponse(response="\n".join(lines) if items else "Ingen aktive opgaver. ✅")

    # -----------------------------------------------------------------------
    # COMPLETE ACTION ITEM
    # -----------------------------------------------------------------------
    if action == "complete_action_item":
        item_id_short = intent.get("action_item_id", "")
        matched_item = None
        search_text = (intent.get("action_description") or req.message).lower()

        for a in action_items:
            if item_id_short and str(a.id).startswith(item_id_short):
                matched_item = a
                break
            if search_text and (search_text in (a.description or "").lower() or search_text in a.action.lower()):
                matched_item = a
                break

        if not matched_item:
            item_list = "\n".join(f"  • {a.action}: {a.description or ''}" for a in action_items[:5])
            return CommandResponse(response=f"Hvilken opgave mener du?\n\n{item_list}")

        return CommandResponse(
            response=f"Skal jeg markere denne opgave som færdig?\n\n📋 **{matched_item.action}** — {matched_item.description or ''}",
            requires_confirmation=True,
            pending_action={"action": "complete_action_item", "item_id": str(matched_item.id)}
        )

    # -----------------------------------------------------------------------
    # LIST CALLS
    # -----------------------------------------------------------------------
    if action == "list_calls":
        status_filter = intent.get("status_filter") or intent.get("filters", {}).get("urgency")
        filtered_calls = calls
        if status_filter and status_filter in ("new", "contacted", "resolved"):
            filtered_calls = [c for c in calls if c.status == status_filter]

        if not filtered_calls:
            return CommandResponse(response="Ingen opkald matcher.")

        lines = [f"**Opkald ({len(filtered_calls)}):**\n"]
        for c in filtered_calls[:8]:
            urgency_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(c.urgency, "⚪")
            lines.append(f"{urgency_icon} **{c.caller_name or 'Ukendt'}** [{c.status}]")
            lines.append(f"   {c.summary[:80] if c.summary else ''}")
            if c.caller_phone:
                lines.append(f"   📞 {c.caller_phone}")

        return CommandResponse(response="\n".join(lines))

    # -----------------------------------------------------------------------
    # UPDATE CALL STATUS
    # -----------------------------------------------------------------------
    if action == "update_call_status":
        call_id_short = intent.get("call_id", "")
        new_status = intent.get("call_status", "contacted")
        notes = intent.get("call_notes")
        search_text = (intent.get("action_description") or req.message).lower()

        matched_call = None
        for c in calls:
            if call_id_short and str(c.id).startswith(call_id_short):
                matched_call = c
                break
            if search_text and (
                search_text in (c.caller_name or "").lower() or
                search_text in (c.summary or "").lower()
            ):
                matched_call = c
                break

        if not matched_call:
            call_list = "\n".join(f"  • {c.caller_name or 'Ukendt'}: {c.summary[:50] if c.summary else ''}" for c in calls[:5])
            return CommandResponse(response=f"Hvilket opkald mener du?\n\n{call_list}")

        return CommandResponse(
            response=f"Skal jeg opdatere opkaldet fra **{matched_call.caller_name or 'ukendt'}** til '{new_status}'?",
            requires_confirmation=True,
            pending_action={
                "action": "update_call_status",
                "call_id": str(matched_call.id),
                "status": new_status,
                "notes": notes,
            }
        )

    # -----------------------------------------------------------------------
    # GET CUSTOMER
    # -----------------------------------------------------------------------
    if action == "get_customer":
        search = (intent.get("customer_name") or intent.get("filters", {}).get("search_text") or req.message).lower()
        matched = [c for c in ctx["customers"] if search in c.name.lower() or search in (c.phone or "").lower()]

        if not matched:
            return CommandResponse(response=f"Fandt ingen kunder der matcher '{search}'.")

        cust = matched[0]
        lines = [
            f"**{cust.name}** [{cust.status}]",
            f"📞 {cust.phone or '—'}  ✉️ {cust.email or '—'}",
        ]
        if cust.address_street:
            lines.append(f"📍 {cust.address_street}, {cust.address_zip or ''} {cust.address_city or ''}")
        if cust.estimated_value:
            lines.append(f"💰 Estimeret værdi: {cust.estimated_value:,.0f} kr.")
        if cust.tags:
            lines.append(f"🏷️ {', '.join(cust.tags)}")

        return CommandResponse(response="\n".join(lines), data={"customer_id": str(cust.id)})

    # -----------------------------------------------------------------------
    # EMAIL ACTIONS (uændret fra original)
    # -----------------------------------------------------------------------
    emails_summary = "\n".join([
        f"  email:{str(e.id)[:8]} [{e.category or '?'}][{e.urgency or '?'}] "
        f"{'ULÆST' if not e.is_read else 'læst'} '{e.subject or '?'}' fra {e.from_address}"
        for e in emails[:30]
    ]) or "Ingen emails."

    if action == "suggest":
        unread = [e for e in emails if not e.is_read]
        high = [e for e in emails if e.urgency == "high"]
        unanswered = [e for e in emails if not e.is_read and e.urgency in ("high", "medium")][:5]
        lines = ["**Forslag til hvad du bør gøre nu:**\n"]
        if high:
            lines.append(f"🔴 **Høj prioritet ({len(high)}):**")
            for e in high[:3]:
                lines.append(f"  • {e.subject or '?'} fra {e.from_address}")
        if unanswered:
            lines.append(f"\n📬 **Ulæste der kræver svar:**")
            for e in unanswered:
                lines.append(f"  • [{e.category or '?'}] {e.subject or '?'} fra {e.from_address}")
        if not high and not unanswered:
            lines.append("Ingen emails kræver øjeblikkelig handling. ✅")
        lines.append(f"\n📊 {len(emails)} emails, {len(unread)} ulæste.")
        return CommandResponse(response="\n".join(lines))

    if action == "summary":
        unread = [e for e in emails if not e.is_read]
        high = [e for e in emails if e.urgency == "high"]
        cats: dict[str, int] = {}
        for e in emails:
            if e.category:
                cats[e.category] = cats.get(e.category, 0) + 1
        cat_lines = ", ".join(f"{v}× {k}" for k, v in sorted(cats.items(), key=lambda x: -x[1]))
        return CommandResponse(response=(
            f"**Indbakke:**\n"
            f"• {len(emails)} emails, {len(unread)} ulæste, {len(high)} hasteemails\n"
            f"• Kategorier: {cat_lines or 'ingen'}"
        ))

    if action == "search":
        matched = _filter_emails(filters, emails)
        if not matched:
            return CommandResponse(response="Ingen emails matcher søgningen.")
        lines = [f"Fandt {len(matched)} email(s):"]
        for e in matched[:10]:
            lines.append(f"• [{e.category or '?'}] {e.subject or '?'} fra {e.from_address}")
        return CommandResponse(response="\n".join(lines), data={"email_ids": [str(e.id) for e in matched]})

    if action == "mark_read":
        matched = _filter_emails(filters, emails)
        if not matched:
            return CommandResponse(response="Ingen emails matcher.")
        for e in matched:
            e.is_read = True
        await db.commit()
        return CommandResponse(response=f"Markerede {len(matched)} email(s) som læst.", actions_taken=[f"Markerede {len(matched)} emails som læst"])

    if action == "generate_reply":
        matched = _filter_emails(filters, emails)
        if not matched:
            return CommandResponse(response="Ingen email at svare på.")
        email = matched[0]
        reply_text = await generate_reply(email, user, db)
        instructions = intent.get("reply_instructions") or ""
        if instructions:
            refine_prompt = f"Tilpas dette email-svar: {instructions}\n\nOriginal: {email.subject}\n{email.body_text or ''}\n\nSvar:\n{reply_text}"
            reply_text = await _call_ollama_generate(refine_prompt)
        suggestion = AiSuggestion(email_id=email.id, suggested_text=reply_text, status="pending")
        db.add(suggestion)
        await db.commit()
        return CommandResponse(
            response=f"Svarudkast til '{email.subject}':\n\n{reply_text}",
            actions_taken=["Svarudkast oprettet"],
            data={"email_id": str(email.id), "suggested_text": reply_text}
        )

    if action == "delete":
        matched = _filter_emails(filters, emails)
        if not matched:
            return CommandResponse(response="Ingen emails at slette.")
        preview = "\n".join(f"• {e.subject or '?'} fra {e.from_address}" for e in matched[:5])
        if len(matched) > 5:
            preview += f"\n... og {len(matched) - 5} mere"
        return CommandResponse(
            response=f"Slet {len(matched)} email(s)?\n\n{preview}",
            requires_confirmation=True,
            pending_action={"action": "delete", "email_ids": [str(e.id) for e in matched]}
        )

    if action == "send":
        to = intent.get("send_to", "")
        subject = intent.get("send_subject", "")
        body = intent.get("send_body", "")
        if not to or not body:
            return CommandResponse(response="Angiv modtager og indhold.")
        return CommandResponse(
            response=f"Send denne email?\n\n**Til:** {to}\n**Emne:** {subject}\n\n{body}",
            requires_confirmation=True,
            pending_action={"action": "send", "send_data": {"to": to, "subject": subject, "body": body}}
        )

    # -----------------------------------------------------------------------
    # CHAT — fri AI-snak med fuld kontekst
    # -----------------------------------------------------------------------
    chat_prompt = (
        f"Du er en hjælpsom assistent for en dansk virksomhed. Svar på dansk.\n\n"
        f"KONTEKST:\n{context_summary}\n\n"
        f"SPØRGSMÅL: {req.message}\n\n"
        f"Svar kortfattet og præcist."
    )
    answer = await _call_ollama_generate(chat_prompt)
    return CommandResponse(response=answer)
