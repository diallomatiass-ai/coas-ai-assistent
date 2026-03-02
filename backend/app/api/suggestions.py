from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.mail_account import MailAccount
from app.models.email_message import EmailMessage
from app.models.ai_suggestion import AiSuggestion
from app.schemas.ai_suggestion import AiSuggestionResponse, SuggestionAction, RefineRequest, RefineResponse
from app.utils.auth import get_current_user

router = APIRouter()


async def _verify_suggestion_access(suggestion_id: UUID, user: User, db: AsyncSession) -> AiSuggestion:
    result = await db.execute(select(AiSuggestion).where(AiSuggestion.id == suggestion_id))
    suggestion = result.scalar_one_or_none()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    # Verify user owns the email's account
    email_result = await db.execute(select(EmailMessage).where(EmailMessage.id == suggestion.email_id))
    email = email_result.scalar_one_or_none()

    account_result = await db.execute(
        select(MailAccount).where(MailAccount.id == email.account_id, MailAccount.user_id == user.id)
    )
    if not account_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    return suggestion


class BulkActionRequest(BaseModel):
    suggestion_ids: list[UUID]
    action: str  # "approve" | "reject"


class BulkActionResponse(BaseModel):
    processed: int
    failed: int
    details: list[dict]


@router.post("/bulk-action", response_model=BulkActionResponse)
async def bulk_suggestion_action(
    data: BulkActionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bulk-godkend eller bulk-afvis flere AI-forslag på én gang."""
    if data.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action skal være 'approve' eller 'reject'")

    if len(data.suggestion_ids) > 50:
        raise HTTPException(status_code=400, detail="Maks 50 forslag pr. bulk-handling")

    processed = 0
    failed = 0
    details = []

    for suggestion_id in data.suggestion_ids:
        try:
            suggestion = await _verify_suggestion_access(suggestion_id, user, db)

            if data.action == "approve":
                suggestion.status = "approved"
                suggestion.edited_text = suggestion.suggested_text
            else:
                suggestion.status = "rejected"

            processed += 1
            details.append({"id": str(suggestion_id), "status": "ok", "new_status": suggestion.status})

            # Log feedback for learning (kun ved godkendelse)
            if data.action == "approve":
                from app.services.learning import log_feedback
                await log_feedback(suggestion, suggestion.suggested_text, db)

        except HTTPException as exc:
            failed += 1
            details.append({"id": str(suggestion_id), "status": "error", "reason": exc.detail})

    await db.commit()
    return BulkActionResponse(processed=processed, failed=failed, details=details)


@router.post("/{suggestion_id}/action", response_model=AiSuggestionResponse)
async def handle_suggestion_action(
    suggestion_id: UUID,
    action: SuggestionAction,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await _verify_suggestion_access(suggestion_id, user, db)

    if action.action == "approve":
        suggestion.status = "approved"
        suggestion.edited_text = suggestion.suggested_text
    elif action.action == "edit":
        if not action.edited_text:
            raise HTTPException(status_code=400, detail="edited_text required for edit action")
        suggestion.status = "edited"
        suggestion.edited_text = action.edited_text
    elif action.action == "reject":
        suggestion.status = "rejected"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await db.commit()
    await db.refresh(suggestion)

    # Log feedback for learning
    if suggestion.status in ("approved", "edited"):
        from app.services.learning import log_feedback
        final_text = suggestion.edited_text or suggestion.suggested_text
        await log_feedback(suggestion, final_text, db)

    return suggestion


@router.post("/{suggestion_id}/send", response_model=AiSuggestionResponse)
async def send_suggestion(
    suggestion_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suggestion = await _verify_suggestion_access(suggestion_id, user, db)

    if suggestion.status not in ("approved", "edited"):
        raise HTTPException(status_code=400, detail="Suggestion must be approved or edited before sending")

    # Get email and account
    email_result = await db.execute(select(EmailMessage).where(EmailMessage.id == suggestion.email_id))
    email = email_result.scalar_one()

    account_result = await db.execute(select(MailAccount).where(MailAccount.id == email.account_id))
    account = account_result.scalar_one()

    # Send via appropriate provider
    reply_text = suggestion.edited_text or suggestion.suggested_text

    if account.provider == "gmail":
        from app.services.mail_gmail import send_reply
        success = await send_reply(account, db, email.from_address, f"Re: {email.subject}", reply_text, email.thread_id)
    elif account.provider == "outlook":
        from app.services.mail_outlook import send_reply
        success = await send_reply(account, db, email.from_address, f"Re: {email.subject}", reply_text, email.thread_id)
    else:
        raise HTTPException(status_code=400, detail="Unknown provider")

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send reply")

    from datetime import datetime, timezone
    suggestion.sent_at = datetime.now(timezone.utc)
    email.is_replied = True
    await db.commit()
    await db.refresh(suggestion)

    return suggestion


@router.post("/{suggestion_id}/refine", response_model=RefineResponse)
async def refine_suggestion(
    suggestion_id: UUID,
    body: RefineRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refine a suggestion based on user instruction via AI chat."""
    suggestion = await _verify_suggestion_access(suggestion_id, user, db)

    current_text = body.current_text or suggestion.edited_text or suggestion.suggested_text

    # Get email for context
    email_result = await db.execute(select(EmailMessage).where(EmailMessage.id == suggestion.email_id))
    email = email_result.scalar_one()

    from app.services.ai_engine import _call_ollama_generate

    prompt = f"""Du er en e-mail assistent. Brugeren vil have dig til at ændre et svarudkast.

## Originalt e-mail
Fra: {email.from_name or email.from_address}
Emne: {email.subject or '(intet emne)'}

## Nuværende svarudkast
{current_text}

## Brugerens instruktion
{body.prompt}

## Regler
- Skriv KUN det nye svarudkast. Ingen forklaringer.
- Bevar sproget (dansk med mindre brugeren beder om andet).
- Maks 200 ord.

## Nyt svarudkast:"""

    refined = await _call_ollama_generate(prompt)
    return RefineResponse(refined_text=refined.strip())
