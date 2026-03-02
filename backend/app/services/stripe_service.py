"""Stripe service — abonnementer, checkout og customer portal."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import stripe

from app.config import settings

if TYPE_CHECKING:
    from app.models.user import User

logger = logging.getLogger(__name__)

stripe.api_key = settings.stripe_secret_key

# Plan → Stripe Price ID mapping
PLAN_PRICE_IDS: dict[str, str] = {
    "starter":  settings.stripe_price_starter,
    "pro":      settings.stripe_price_pro,
    "business": settings.stripe_price_business,
}

# Stripe Price ID → plan navn (reverse lookup)
PRICE_PLAN_MAP: dict[str, str] = {v: k for k, v in PLAN_PRICE_IDS.items() if v}

PLAN_LABELS = {
    "free":     "Gratis",
    "starter":  "Starter",
    "pro":      "Pro",
    "business": "Business",
}

PLAN_PRICES_DKK = {
    "free":     0,
    "starter":  499,
    "pro":      999,
    "business": 2499,
}

PLAN_FEATURES = {
    "free": ["1 mailkonto", "50 AI-svar/md", "Basis klassificering"],
    "starter": ["1 bruger", "1 mailkonto", "500 AI-svar/md", "Skabeloner", "Videnbase"],
    "pro": ["5 brugere", "3 mailkonti", "2.000 AI-svar/md", "AI Secretary", "Kalender-sync"],
    "business": ["20 brugere", "10 mailkonti", "Ubegrænsede svar", "Prioriteret support", "API-adgang"],
}


async def get_or_create_customer(user: "User") -> str:
    """Hent eksisterende Stripe customer eller opret en ny.

    Returns:
        Stripe customer ID (cus_...)
    """
    if user.stripe_customer_id:
        return user.stripe_customer_id

    def _create():
        return stripe.Customer.create(
            email=user.email,
            name=user.name,
            metadata={"user_id": str(user.id), "company": user.company_name or ""},
        )

    customer = await asyncio.to_thread(_create)
    return customer.id


async def create_checkout_session(user: "User", plan: str) -> str:
    """Opret en Stripe Checkout session og returnér redirect URL.

    Args:
        user: Den bruger der skal opgradere.
        plan: 'starter', 'pro' eller 'business'.

    Returns:
        Checkout session URL.
    """
    price_id = PLAN_PRICE_IDS.get(plan)
    if not price_id:
        raise ValueError(f"Ukendt plan: {plan}. Vælg: starter, pro, business")

    customer_id = await get_or_create_customer(user)

    def _create():
        params: dict = {
            "customer": customer_id,
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": settings.stripe_success_url,
            "cancel_url": settings.stripe_cancel_url,
            "subscription_data": {
                "trial_period_days": 14,
                "metadata": {"user_id": str(user.id), "plan": plan},
            },
            "metadata": {"user_id": str(user.id), "plan": plan},
            "allow_promotion_codes": True,
            "billing_address_collection": "required",
            "locale": "da",
        }
        # Hvis brugeren allerede har et aktivt abonnement → skift plan
        if user.stripe_subscription_id:
            params.pop("subscription_data", None)
            params["mode"] = "subscription"
        return stripe.checkout.Session.create(**params)

    session = await asyncio.to_thread(_create)
    return session.url


async def create_portal_session(user: "User") -> str:
    """Opret Stripe Customer Portal session (administrer abonnement, faktura, annuller).

    Returns:
        Portal URL.
    """
    if not user.stripe_customer_id:
        raise ValueError("Brugeren har ingen Stripe customer — opret abonnement først")

    def _create():
        return stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=settings.stripe_cancel_url.replace("?canceled=true", ""),
        )

    session = await asyncio.to_thread(_create)
    return session.url


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verificér og parse Stripe webhook-signatur.

    Raises:
        stripe.error.SignatureVerificationError ved ugyldig signatur.
    """
    return stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )


def get_plan_from_price_id(price_id: str) -> str:
    """Returnér plan-navn fra Stripe Price ID."""
    return PRICE_PLAN_MAP.get(price_id, "starter")
