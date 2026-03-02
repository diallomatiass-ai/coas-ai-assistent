"""Twilio SMS service til booking-bekræftelser og opfølgninger."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _get_twilio_client():
    """Lav Twilio-klient — importeres lazy så manglende credentials ikke crasher opstart."""
    try:
        from twilio.rest import Client
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            raise ValueError("Twilio credentials mangler i .env (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)")
        return Client(settings.twilio_account_sid, settings.twilio_auth_token)
    except ImportError:
        raise RuntimeError("twilio-pakken er ikke installeret — kør: pip install twilio")


def send_sms(to: str, body: str) -> bool:
    """Send en SMS via Twilio.

    Args:
        to:   Modtagerens telefonnummer (E.164 format, f.eks. +4512345678)
        body: SMS-teksten (maks 160 tegn pr. SMS-segment)

    Returns:
        True ved succes, False ved fejl.
    """
    try:
        client = _get_twilio_client()
        message = client.messages.create(
            body=body,
            from_=settings.twilio_phone_number,
            to=to,
        )
        logger.info("SMS sendt til %s — SID: %s", to, message.sid)
        return True
    except Exception as exc:
        logger.error("SMS afsendelse fejlede til %s: %s", to, exc)
        return False


def send_booking_confirmation(
    to: str,
    caller_name: str,
    business_name: str,
    summary: str,
) -> bool:
    """Send en booking-bekræftelse via SMS.

    Args:
        to:            Modtagerens telefonnummer.
        caller_name:   Kundens navn.
        business_name: Virksomhedens navn.
        summary:       Kort sammenfatning af opkaldet/bookingen.

    Returns:
        True ved succes.
    """
    name_part = f"Hej {caller_name}, " if caller_name else "Hej, "
    body = (
        f"{name_part}tak for din henvendelse til {business_name}. "
        f"{summary} "
        f"Vi vender tilbage hurtigst muligt."
    )
    # SMS maks 160 tegn pr. segment — trim hvis nødvendig
    if len(body) > 320:
        body = body[:317] + "..."
    return send_sms(to, body)


def send_followup_sms(to: str, business_name: str, message: str) -> bool:
    """Send en opfølgnings-SMS til en kunde.

    Args:
        to:            Modtagerens telefonnummer.
        business_name: Virksomhedens navn (til afsender-identifikation).
        message:       Opfølgningsteksten.

    Returns:
        True ved succes.
    """
    body = f"{business_name}: {message}"
    if len(body) > 320:
        body = body[:317] + "..."
    return send_sms(to, body)
