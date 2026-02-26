from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.mail_account import MailAccount
from app.schemas.mail_account import MailAccountResponse
from app.utils.auth import get_current_user
from app.utils.encryption import encrypt_token
from app.config import settings

router = APIRouter()


def _get_base_url(request: Request) -> str:
    """Build base URL from request, respecting proxy headers."""
    proto = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "localhost")
    return f"{proto}://{host}"


@router.get("/gmail/connect")
async def gmail_connect(request: Request, user: User = Depends(get_current_user)):
    """Return Gmail OAuth2 authorization URL."""
    base = _get_base_url(request)
    redirect_uri = settings.gmail_redirect_uri or f"{base}/api/webhooks/gmail/callback"

    scopes = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/calendar"
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={settings.gmail_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state={user.id}"
    )
    return {"auth_url": url}


@router.get("/gmail/callback")
async def gmail_callback(code: str, state: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Gmail OAuth2 callback."""
    import httpx
    from datetime import datetime, timezone

    base = _get_base_url(request)
    redirect_uri = settings.gmail_redirect_uri or f"{base}/api/webhooks/gmail/callback"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        if resp.status_code != 200:
            return RedirectResponse(f"{base}/settings?error=gmail_token_failed")
        tokens = resp.json()

    # Get user email from Gmail profile
    async with httpx.AsyncClient() as client:
        profile_resp = await client.get(
            "https://www.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        profile = profile_resp.json()

    from uuid import UUID
    user_id = state
    email_address = profile.get("emailAddress", "")
    expires_at = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + tokens.get("expires_in", 3600),
        tz=timezone.utc,
    )

    # Check if account already exists for this user+provider+email (upsert)
    existing = await db.execute(
        select(MailAccount).where(
            MailAccount.user_id == UUID(user_id),
            MailAccount.provider == "gmail",
            MailAccount.email_address == email_address,
        )
    )
    account = existing.scalar_one_or_none()

    if account:
        account.encrypted_access_token = encrypt_token(tokens["access_token"])
        account.encrypted_refresh_token = encrypt_token(tokens.get("refresh_token", ""))
        account.token_expires_at = expires_at
        account.is_active = True
    else:
        account = MailAccount(
            user_id=user_id,
            provider="gmail",
            email_address=email_address,
            encrypted_access_token=encrypt_token(tokens["access_token"]),
            encrypted_refresh_token=encrypt_token(tokens.get("refresh_token", "")),
            token_expires_at=expires_at,
        )
        db.add(account)

    await db.commit()
    return RedirectResponse(f"{base}/settings?connected=gmail")


@router.get("/outlook/connect")
async def outlook_connect(request: Request, user: User = Depends(get_current_user)):
    """Return Outlook OAuth2 authorization URL."""
    base = _get_base_url(request)
    redirect_uri = settings.outlook_redirect_uri or f"{base}/api/webhooks/outlook/callback"

    scopes = "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Calendars.ReadWrite offline_access"
    url = (
        f"https://login.microsoftonline.com/{settings.outlook_tenant_id}/oauth2/v2.0/authorize?"
        f"client_id={settings.outlook_client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"state={user.id}"
    )
    return {"auth_url": url}


@router.get("/outlook/callback")
async def outlook_callback(code: str, state: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Outlook OAuth2 callback."""
    import httpx
    from datetime import datetime, timezone

    base = _get_base_url(request)
    redirect_uri = settings.outlook_redirect_uri or f"{base}/api/webhooks/outlook/callback"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{settings.outlook_tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": settings.outlook_client_id,
                "client_secret": settings.outlook_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "scope": "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send https://graph.microsoft.com/Calendars.ReadWrite offline_access",
            },
        )
        if resp.status_code != 200:
            return RedirectResponse(f"{base}/settings?error=outlook_token_failed")
        tokens = resp.json()

    # Get user email from Graph
    async with httpx.AsyncClient() as client:
        me_resp = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me = me_resp.json()

    from uuid import UUID
    user_id = state
    email_address = me.get("mail") or me.get("userPrincipalName", "")
    expires_at = datetime.fromtimestamp(
        datetime.now(timezone.utc).timestamp() + tokens.get("expires_in", 3600),
        tz=timezone.utc,
    )

    # Check if account already exists (upsert)
    existing = await db.execute(
        select(MailAccount).where(
            MailAccount.user_id == UUID(user_id),
            MailAccount.provider == "outlook",
            MailAccount.email_address == email_address,
        )
    )
    account = existing.scalar_one_or_none()

    if account:
        account.encrypted_access_token = encrypt_token(tokens["access_token"])
        account.encrypted_refresh_token = encrypt_token(tokens["refresh_token"])
        account.token_expires_at = expires_at
        account.is_active = True
    else:
        account = MailAccount(
            user_id=user_id,
            provider="outlook",
            email_address=email_address,
            encrypted_access_token=encrypt_token(tokens["access_token"]),
            encrypted_refresh_token=encrypt_token(tokens["refresh_token"]),
            token_expires_at=expires_at,
        )
        db.add(account)

    await db.commit()
    return RedirectResponse(f"{base}/settings?connected=outlook")


@router.get("/accounts", response_model=list[MailAccountResponse])
async def list_accounts(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MailAccount).where(MailAccount.user_id == user.id)
    )
    return result.scalars().all()


@router.delete("/accounts/{account_id}", status_code=204)
async def disconnect_account(
    account_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID
    result = await db.execute(
        select(MailAccount).where(MailAccount.id == UUID(account_id), MailAccount.user_id == user.id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    await db.delete(account)
    await db.commit()
