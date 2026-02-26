"""
Kalender-service til Google Calendar og Microsoft Outlook.
Understøtter opret, opdater og slet kalenderbegivenheder via OAuth-tokens.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx

from app.models.mail_account import MailAccount
from app.models.calendar_event import CalendarEvent
from app.services.token_manager import get_valid_token

logger = logging.getLogger(__name__)


def _google_event_body(event: CalendarEvent) -> dict:
    """Byg Google Calendar API request body."""
    return {
        "summary": event.title,
        "description": event.description or "",
        "start": {
            "dateTime": event.start_time.isoformat(),
            "timeZone": "Europe/Copenhagen",
        },
        "end": {
            "dateTime": event.end_time.isoformat(),
            "timeZone": "Europe/Copenhagen",
        },
    }


def _outlook_event_body(event: CalendarEvent) -> dict:
    """Byg Microsoft Graph API request body."""
    return {
        "subject": event.title,
        "body": {
            "contentType": "text",
            "content": event.description or "",
        },
        "start": {
            "dateTime": event.start_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "Romance Standard Time",  # Copenhagen
        },
        "end": {
            "dateTime": event.end_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "timeZone": "Romance Standard Time",
        },
    }


class GoogleCalendarService:
    """Google Calendar API v3 klient."""

    BASE_URL = "https://www.googleapis.com/calendar/v3"
    CALENDAR_ID = "primary"

    def __init__(self, account: MailAccount, db):
        self.account = account
        self.db = db

    async def _get_headers(self) -> dict:
        token = await get_valid_token(self.account, self.db)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def create_event(self, event: CalendarEvent) -> str | None:
        """Opret begivenhed i Google Calendar. Returnerer external_event_id."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.BASE_URL}/calendars/{self.CALENDAR_ID}/events",
                    headers=headers,
                    json=_google_event_body(event),
                    timeout=15,
                )
                if resp.status_code in (200, 201):
                    return resp.json().get("id")
                logger.warning("Google Calendar create fejlede: %s %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Google Calendar create exception: %s", e)
        return None

    async def update_event(self, external_id: str, event: CalendarEvent) -> bool:
        """Opdater eksisterende begivenhed."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                resp = await client.put(
                    f"{self.BASE_URL}/calendars/{self.CALENDAR_ID}/events/{external_id}",
                    headers=headers,
                    json=_google_event_body(event),
                    timeout=15,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Google Calendar update exception: %s", e)
        return False

    async def delete_event(self, external_id: str) -> bool:
        """Slet begivenhed fra Google Calendar."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"{self.BASE_URL}/calendars/{self.CALENDAR_ID}/events/{external_id}",
                    headers=headers,
                    timeout=15,
                )
                return resp.status_code in (200, 204)
        except Exception as e:
            logger.error("Google Calendar delete exception: %s", e)
        return False

    async def list_events(self, start: datetime, end: datetime) -> list[dict]:
        """Hent begivenheder fra Google Calendar i tidsperiode."""
        try:
            headers = await self._get_headers()
            params = {
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
            }
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self.BASE_URL}/calendars/{self.CALENDAR_ID}/events",
                    headers=headers,
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 200:
                    return resp.json().get("items", [])
        except Exception as e:
            logger.error("Google Calendar list exception: %s", e)
        return []


class OutlookCalendarService:
    """Microsoft Graph Calendar API klient."""

    BASE_URL = "https://graph.microsoft.com/v1.0/me/events"

    def __init__(self, account: MailAccount, db):
        self.account = account
        self.db = db

    async def _get_headers(self) -> dict:
        token = await get_valid_token(self.account, self.db)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async def create_event(self, event: CalendarEvent) -> str | None:
        """Opret begivenhed i Outlook Calendar. Returnerer external_event_id."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.BASE_URL,
                    headers=headers,
                    json=_outlook_event_body(event),
                    timeout=15,
                )
                if resp.status_code == 201:
                    return resp.json().get("id")
                logger.warning("Outlook Calendar create fejlede: %s %s", resp.status_code, resp.text)
        except Exception as e:
            logger.error("Outlook Calendar create exception: %s", e)
        return None

    async def update_event(self, external_id: str, event: CalendarEvent) -> bool:
        """Opdater eksisterende begivenhed."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                resp = await client.patch(
                    f"{self.BASE_URL}/{external_id}",
                    headers=headers,
                    json=_outlook_event_body(event),
                    timeout=15,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error("Outlook Calendar update exception: %s", e)
        return False

    async def delete_event(self, external_id: str) -> bool:
        """Slet begivenhed fra Outlook Calendar."""
        try:
            headers = await self._get_headers()
            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"{self.BASE_URL}/{external_id}",
                    headers=headers,
                    timeout=15,
                )
                return resp.status_code == 204
        except Exception as e:
            logger.error("Outlook Calendar delete exception: %s", e)
        return False

    async def list_events(self, start: datetime, end: datetime) -> list[dict]:
        """Hent begivenheder fra Outlook i tidsperiode."""
        try:
            headers = await self._get_headers()
            params = {
                "$filter": f"start/dateTime ge '{start.strftime('%Y-%m-%dT%H:%M:%S')}' and end/dateTime le '{end.strftime('%Y-%m-%dT%H:%M:%S')}'",
                "$orderby": "start/dateTime",
                "$select": "id,subject,body,start,end",
            }
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    self.BASE_URL,
                    headers=headers,
                    params=params,
                    timeout=15,
                )
                if resp.status_code == 200:
                    return resp.json().get("value", [])
        except Exception as e:
            logger.error("Outlook Calendar list exception: %s", e)
        return []


def get_calendar_service(account: MailAccount, db):
    """Factory: returnér rigtig service baseret på provider."""
    if account.provider == "gmail":
        return GoogleCalendarService(account, db)
    elif account.provider == "outlook":
        return OutlookCalendarService(account, db)
    raise ValueError(f"Ukendt provider: {account.provider}")
