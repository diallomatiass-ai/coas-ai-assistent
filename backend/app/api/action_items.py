import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.mail_account import MailAccount
from app.models.action_item import ActionItem
from app.models.calendar_event import CalendarEvent
from app.utils.auth import get_current_user
from app.services.calendar_service import get_calendar_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Kalender sync hjælpefunktioner
# ---------------------------------------------------------------------------

def _action_to_event_title(item: ActionItem) -> str:
    action_labels = {
        "ring_tilbage": "Ring tilbage",
        "send_tilbud": "Send tilbud",
        "følg_op": "Følg op",
        "send_faktura": "Send faktura",
        "book_møde": "Book møde",
    }
    label = action_labels.get(item.action, item.action)
    return f"📋 {label}"


async def _get_user_account(user_id: uuid.UUID, db: AsyncSession) -> MailAccount | None:
    result = await db.execute(
        select(MailAccount).where(
            MailAccount.user_id == user_id,
            MailAccount.is_active == True,
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def _sync_action_item_to_calendar(item: ActionItem, user: User, db: AsyncSession) -> None:
    """Opret eller opdater kalenderbegivenhed for et action item med deadline."""
    if not item.deadline:
        return

    account = await _get_user_account(user.id, db)
    if not account:
        return

    # Find eksisterende CalendarEvent for dette action item
    existing_result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.action_item_id == item.id)
    )
    cal_event = existing_result.scalar_one_or_none()

    start = item.deadline
    end = start + timedelta(hours=1)
    title = _action_to_event_title(item)
    description = item.description or ""

    if cal_event:
        cal_event.title = title
        cal_event.description = description
        cal_event.start_time = start
        cal_event.end_time = end
        await db.commit()
        await db.refresh(cal_event)
        if cal_event.external_event_id:
            try:
                svc = get_calendar_service(account, db)
                await svc.update_event(cal_event.external_event_id, cal_event)
            except Exception:
                pass
    else:
        cal_event = CalendarEvent(
            user_id=user.id,
            title=title,
            description=description,
            start_time=start,
            end_time=end,
            action_item_id=item.id,
            event_type="action_item",
        )
        db.add(cal_event)
        await db.commit()
        await db.refresh(cal_event)
        try:
            svc = get_calendar_service(account, db)
            external_id = await svc.create_event(cal_event)
            if external_id:
                cal_event.external_event_id = external_id
                cal_event.provider = account.provider
                cal_event.account_id = account.id
                await db.commit()
        except Exception:
            pass


async def _delete_action_item_calendar(item_id: uuid.UUID, db: AsyncSession) -> None:
    """Slet tilknyttet kalenderbegivenhed når action item slettes."""
    existing_result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.action_item_id == item_id)
    )
    cal_event = existing_result.scalar_one_or_none()
    if not cal_event:
        return

    external_id = cal_event.external_event_id
    account_id = cal_event.account_id

    await db.delete(cal_event)
    await db.commit()

    if external_id and account_id:
        acc_result = await db.execute(
            select(MailAccount).where(MailAccount.id == account_id)
        )
        account = acc_result.scalar_one_or_none()
        if account:
            try:
                svc = get_calendar_service(account, db)
                await svc.delete_event(external_id)
            except Exception:
                pass


class ActionItemCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    call_id: uuid.UUID | None = None
    action: str
    description: str | None = None
    status: str = "pending"
    deadline: datetime | None = None


class ActionItemUpdate(BaseModel):
    action: str | None = None
    description: str | None = None
    status: str | None = None
    deadline: datetime | None = None


class ActionItemResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    customer_id: uuid.UUID | None
    call_id: uuid.UUID | None
    action: str
    description: str | None
    status: str
    deadline: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ActionItemResponse])
async def list_action_items(
    status: str | None = Query(None, description="Filtrer på status: pending, done, overdue"),
    customer_id: uuid.UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste action items for den aktuelle bruger."""
    query = select(ActionItem).where(ActionItem.user_id == user.id)

    if status:
        query = query.where(ActionItem.status == status)
    if customer_id:
        query = query.where(ActionItem.customer_id == customer_id)

    query = query.order_by(ActionItem.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=ActionItemResponse, status_code=201)
async def create_action_item(
    data: ActionItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Opret nyt action item."""
    item = ActionItem(
        user_id=user.id,
        customer_id=data.customer_id,
        call_id=data.call_id,
        action=data.action,
        description=data.description,
        status=data.status,
        deadline=data.deadline,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Sync til kalender (best-effort, kun hvis deadline er sat)
    await _sync_action_item_to_calendar(item, user, db)

    return item


@router.put("/{item_id}", response_model=ActionItemResponse)
async def update_action_item(
    item_id: uuid.UUID,
    data: ActionItemUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Opdater status, deadline eller beskrivelse på et action item."""
    result = await db.execute(
        select(ActionItem).where(ActionItem.id == item_id, ActionItem.user_id == user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item ikke fundet")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)

    await db.commit()
    await db.refresh(item)

    # Sync opdatering til kalender
    await _sync_action_item_to_calendar(item, user, db)

    return item


@router.delete("/{item_id}", status_code=204)
async def delete_action_item(
    item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Slet et action item."""
    result = await db.execute(
        select(ActionItem).where(ActionItem.id == item_id, ActionItem.user_id == user.id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Action item ikke fundet")

    # Slet tilknyttet kalenderbegivenhed
    await _delete_action_item_calendar(item.id, db)

    await db.delete(item)
    await db.commit()
