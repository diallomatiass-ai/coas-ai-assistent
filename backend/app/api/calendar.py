"""
Kalender API — CRUD for CalendarEvent + status endpoint.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.mail_account import MailAccount
from app.models.calendar_event import CalendarEvent
from app.utils.auth import get_current_user
from app.services.calendar_service import get_calendar_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CalendarEventCreate(BaseModel):
    title: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    action_item_id: uuid.UUID | None = None
    call_id: uuid.UUID | None = None
    event_type: str = "manual"


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


class CalendarEventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID | None
    external_event_id: str | None
    provider: str | None
    title: str
    description: str | None
    start_time: datetime
    end_time: datetime
    action_item_id: uuid.UUID | None
    call_id: uuid.UUID | None
    event_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_active_account(user: User, db: AsyncSession) -> MailAccount | None:
    """Returnér brugerens første aktive mailkonto med kalender-adgang."""
    result = await db.execute(
        select(MailAccount).where(
            MailAccount.user_id == user.id,
            MailAccount.is_active == True,
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _sync_create(account: MailAccount, event: CalendarEvent, db: AsyncSession) -> None:
    """Forsøg at synkronisere et nyt event til ekstern kalender."""
    try:
        svc = get_calendar_service(account, db)
        external_id = await svc.create_event(event)
        if external_id:
            event.external_event_id = external_id
            event.provider = account.provider
            event.account_id = account.id
            await db.commit()
    except Exception:
        pass  # Sync er best-effort — lokalt event gemmes altid


async def _sync_update(account: MailAccount, event: CalendarEvent, db: AsyncSession) -> None:
    """Forsøg at synkronisere en opdatering til ekstern kalender."""
    if not event.external_event_id:
        return
    try:
        svc = get_calendar_service(account, db)
        await svc.update_event(event.external_event_id, event)
    except Exception:
        pass


async def _sync_delete(account: MailAccount, external_id: str, db: AsyncSession) -> None:
    """Forsøg at slette event fra ekstern kalender."""
    try:
        svc = get_calendar_service(account, db)
        await svc.delete_event(external_id)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def calendar_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returnér om kalender er forbundet og hvilken udbyder."""
    account = await _get_active_account(user, db)
    if not account:
        return {"connected": False, "provider": None, "email": None}
    return {
        "connected": True,
        "provider": account.provider,
        "email": account.email_address,
    }


@router.get("/events", response_model=list[CalendarEventResponse])
async def list_calendar_events(
    start: datetime | None = Query(None, description="ISO8601 startdato"),
    end: datetime | None = Query(None, description="ISO8601 slutdato"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hent kalenderbegivenheder i tidsperiode (default: denne uge)."""
    now = datetime.now(timezone.utc)
    if start is None:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if end is None:
        end = start + timedelta(days=30)

    query = select(CalendarEvent).where(
        CalendarEvent.user_id == user.id,
        CalendarEvent.start_time >= start,
        CalendarEvent.start_time <= end,
    ).order_by(CalendarEvent.start_time)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/events", response_model=CalendarEventResponse, status_code=201)
async def create_calendar_event(
    data: CalendarEventCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Opret kalenderbegivenhed og synkroniser til Google/Outlook."""
    event = CalendarEvent(
        user_id=user.id,
        title=data.title,
        description=data.description,
        start_time=data.start_time,
        end_time=data.end_time,
        action_item_id=data.action_item_id,
        call_id=data.call_id,
        event_type=data.event_type,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # Sync til ekstern kalender (best-effort)
    account = await _get_active_account(user, db)
    if account:
        await _sync_create(account, event, db)
        await db.refresh(event)

    return event


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: uuid.UUID,
    data: CalendarEventUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Opdater kalenderbegivenhed."""
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Begivenhed ikke fundet")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)

    # Sync update til ekstern kalender
    account = await _get_active_account(user, db)
    if account and event.external_event_id:
        await _sync_update(account, event, db)

    return event


@router.delete("/events/{event_id}", status_code=204)
async def delete_calendar_event(
    event_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Slet kalenderbegivenhed lokalt og fra ekstern kalender."""
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user.id,
        )
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Begivenhed ikke fundet")

    external_id = event.external_event_id
    provider = event.provider
    account_id = event.account_id

    await db.delete(event)
    await db.commit()

    # Sync slet til ekstern kalender
    if external_id and account_id:
        acc_result = await db.execute(
            select(MailAccount).where(MailAccount.id == account_id)
        )
        account = acc_result.scalar_one_or_none()
        if account:
            await _sync_delete(account, external_id, db)
