"""Mail sync orchestrator — pulls new messages and persists them."""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_message import EmailMessage
from app.models.mail_account import MailAccount
from app.services import mail_gmail, mail_outlook

logger = logging.getLogger(__name__)


async def sync_account(account: MailAccount, db: AsyncSession) -> int:
    """
    Sync a single mail account.

    Fetches new messages via the provider-specific client, de-duplicates
    against existing records by provider_id, and persists new messages.

    Returns the count of newly saved messages.
    """
    # Select the correct provider module
    if account.provider == "gmail":
        provider = mail_gmail
    elif account.provider == "outlook":
        provider = mail_outlook
    else:
        logger.warning(
            "Unknown provider '%s' for account %s — skipping",
            account.provider,
            account.email_address,
        )
        return 0

    try:
        messages = await provider.fetch_messages(account, db)
    except Exception:
        logger.exception(
            "Failed to fetch messages for %s (%s)",
            account.email_address,
            account.provider,
        )
        return 0

    if not messages:
        return 0

    # Collect provider_ids to check for duplicates in one query
    incoming_ids = [m["provider_id"] for m in messages]
    existing_result = await db.execute(
        select(EmailMessage.provider_id).where(
            EmailMessage.account_id == account.id,
            EmailMessage.provider_id.in_(incoming_ids),
        )
    )
    existing_ids: set[str] = {row[0] for row in existing_result.all()}

    new_count = 0
    for msg in messages:
        if msg["provider_id"] in existing_ids:
            continue

        email = EmailMessage(
            account_id=account.id,
            provider_id=msg["provider_id"],
            thread_id=msg.get("thread_id"),
            from_address=msg["from_address"],
            from_name=msg.get("from_name", ""),
            to_address=msg["to_address"],
            subject=msg.get("subject", ""),
            body_text=msg.get("body_text", ""),
            body_html=msg.get("body_html", ""),
            received_at=msg.get("received_at"),
            is_read=False,
            is_replied=False,
            processed=False,
        )
        db.add(email)
        new_count += 1

    if new_count:
        await db.commit()

        # Trigger AI processing for each new email
        from app.tasks.worker import process_single_email
        for msg in messages:
            if msg["provider_id"] not in existing_ids:
                # Find the email we just saved
                saved = await db.execute(
                    select(EmailMessage).where(
                        EmailMessage.account_id == account.id,
                        EmailMessage.provider_id == msg["provider_id"],
                    )
                )
                saved_email = saved.scalar_one_or_none()
                if saved_email:
                    process_single_email.delay(str(saved_email.id))

        # Notificér frontend via WebSocket (best-effort)
        try:
            from app.api.ws import publish_ws_event
            publish_ws_event(
                str(account.user_id),
                {"type": "new_email", "count": new_count, "account": account.email_address},
            )
        except Exception:
            pass

    logger.info(
        "Synced %s — %d new / %d fetched / %d duplicates skipped",
        account.email_address,
        new_count,
        len(messages),
        len(messages) - new_count,
    )
    return new_count


async def sync_all_accounts(db: AsyncSession) -> None:
    """
    Sync every active mail account.

    Iterates through all active MailAccount rows and syncs each one
    sequentially. Errors on individual accounts are logged but do not
    stop the overall sync run.
    """
    result = await db.execute(
        select(MailAccount).where(MailAccount.is_active.is_(True))
    )
    accounts = result.scalars().all()

    if not accounts:
        logger.debug("No active mail accounts to sync")
        return

    total_new = 0
    for account in accounts:
        count = await sync_account(account, db)
        total_new += count

    logger.info(
        "Sync run complete — %d accounts, %d new messages total",
        len(accounts),
        total_new,
    )
