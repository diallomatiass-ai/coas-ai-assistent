"""
Kundematching og -oprettelse baseret på opkaldsdata.
Bruges til automatisk at linke opkald til eksisterende kunder
eller oprette nye kunder ved første kontakt.
"""

import logging
import re
import uuid

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.email_message import EmailMessage
from app.models.secretary_call import SecretaryCall
from app.models.action_item import ActionItem

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Normalisér telefonnummer til rent ciffer-format for sammenligning."""
    digits = re.sub(r'\D', '', phone)
    # Fjern dansk landekode 45 hvis nummeret starter med det og er langt nok
    if digits.startswith('45') and len(digits) > 8:
        digits = digits[2:]
    return digits


async def find_or_create_from_call(
    caller_name: str | None,
    caller_phone: str | None,
    caller_address: str | None,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Customer:
    """
    Find eksisterende kunde baseret på telefonnummer eller navn,
    eller opret en ny kunde hvis ingen match findes.
    Returnerer Customer-objektet (uflushed commit — caller håndterer commit).
    """
    # Forsøg at matche på telefonnummer (mest præcist)
    if caller_phone:
        result = await db.execute(
            select(Customer).where(
                Customer.user_id == user_id,
                Customer.phone == caller_phone,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.debug("Matched customer by phone: %s", existing.id)
            return existing

    # Forsøg at matche på navn hvis intet phone-match
    if caller_name:
        result = await db.execute(
            select(Customer).where(
                Customer.user_id == user_id,
                Customer.name.ilike(caller_name.strip()),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.debug("Matched customer by name: %s", existing.id)
            # Opdater telefon hvis vi nu kender den
            if caller_phone and not existing.phone:
                existing.phone = caller_phone
            return existing

    # Ingen match — opret ny kunde
    new_customer = Customer(
        user_id=user_id,
        name=caller_name or "Ukendt",
        phone=caller_phone,
        address_street=caller_address,
        source="call",
        status="aktiv",
        tags=[],
    )
    db.add(new_customer)
    await db.flush()  # Giv ID uden at committe
    logger.debug("Created new customer from call: %s", new_customer.id)
    return new_customer


async def merge_customers(
    primary_id: uuid.UUID,
    other_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession,
) -> Customer:
    """
    Flet two kunder: behold primary, flyt al data fra other til primary.
    Sletter other-kunden efter flytning.
    Caller er ansvarlig for db.commit() efter kald.
    """
    if primary_id == other_id:
        raise ValueError("Kan ikke flette en kunde med sig selv")

    # Hent begge kunder og verificér ejerskab
    primary_result = await db.execute(
        select(Customer).where(Customer.id == primary_id, Customer.user_id == user_id)
    )
    primary = primary_result.scalar_one_or_none()
    if not primary:
        raise ValueError(f"Primær kunde {primary_id} ikke fundet")

    other_result = await db.execute(
        select(Customer).where(Customer.id == other_id, Customer.user_id == user_id)
    )
    other = other_result.scalar_one_or_none()
    if not other:
        raise ValueError(f"Anden kunde {other_id} ikke fundet")

    # Flyt emails
    email_result = await db.execute(
        select(EmailMessage).where(EmailMessage.customer_id == other_id)
    )
    for email in email_result.scalars().all():
        email.customer_id = primary_id

    # Flyt opkald
    call_result = await db.execute(
        select(SecretaryCall).where(SecretaryCall.customer_id == other_id)
    )
    for call in call_result.scalars().all():
        call.customer_id = primary_id

    # Flyt action items
    action_result = await db.execute(
        select(ActionItem).where(ActionItem.customer_id == other_id)
    )
    for item in action_result.scalars().all():
        item.customer_id = primary_id

    # Berik primary med manglende data fra other
    if not primary.phone and other.phone:
        primary.phone = other.phone
    if not primary.email and other.email:
        primary.email = other.email
    if not primary.address_street and other.address_street:
        primary.address_street = other.address_street
        primary.address_zip = other.address_zip
        primary.address_city = other.address_city
    if not primary.estimated_value and other.estimated_value:
        primary.estimated_value = other.estimated_value
    if not primary.notes and other.notes:
        primary.notes = other.notes

    # Flet tags (union uden dubletter)
    combined_tags = list(set((primary.tags or []) + (other.tags or [])))
    primary.tags = combined_tags

    # Slet other-kunden
    await db.delete(other)
    await db.flush()

    logger.info("Merged customer %s into %s", other_id, primary_id)
    return primary
