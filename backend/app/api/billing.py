"""Billing API — Stripe abonnementer, checkout og webhook."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.utils.auth import get_current_user
from app.services import stripe_service
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str  # starter | pro | business


class CheckoutResponse(BaseModel):
    url: str


class PortalResponse(BaseModel):
    url: str


class SubscriptionStatus(BaseModel):
    plan: str
    status: str
    label: str
    price_dkk: int
    features: list[str]
    trial_ends_at: datetime | None
    subscription_ends_at: datetime | None
    stripe_customer_id: str | None
    has_active_subscription: bool


class PlanInfo(BaseModel):
    id: str
    label: str
    price_dkk: int
    features: list[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/plans", response_model=list[PlanInfo])
async def list_plans():
    """List alle tilgængelige abonnementsplaner."""
    return [
        PlanInfo(
            id=plan_id,
            label=stripe_service.PLAN_LABELS[plan_id],
            price_dkk=stripe_service.PLAN_PRICES_DKK[plan_id],
            features=stripe_service.PLAN_FEATURES[plan_id],
        )
        for plan_id in ["free", "starter", "pro", "business"]
    ]


@router.get("/subscription", response_model=SubscriptionStatus)
async def get_subscription(user: User = Depends(get_current_user)):
    """Hent den aktuelle brugers abonnementsstatus."""
    plan = user.plan or "free"
    status = user.subscription_status or "free"
    is_active = status in ("active", "trialing")

    return SubscriptionStatus(
        plan=plan,
        status=status,
        label=stripe_service.PLAN_LABELS.get(plan, "Gratis"),
        price_dkk=stripe_service.PLAN_PRICES_DKK.get(plan, 0),
        features=stripe_service.PLAN_FEATURES.get(plan, []),
        trial_ends_at=user.trial_ends_at,
        subscription_ends_at=user.subscription_ends_at,
        stripe_customer_id=user.stripe_customer_id,
        has_active_subscription=is_active,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    data: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Opret Stripe Checkout session — returnerer URL til betaling."""
    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe er ikke konfigureret. Indsæt STRIPE_SECRET_KEY i .env.",
        )

    if data.plan not in ("starter", "pro", "business"):
        raise HTTPException(status_code=400, detail="Ugyldig plan. Vælg: starter, pro, business")

    try:
        url = await stripe_service.create_checkout_session(user, data.plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Stripe checkout fejl: %s", exc)
        raise HTTPException(status_code=503, detail="Stripe fejl — prøv igen")

    # Gem stripe_customer_id hvis ny customer blev oprettet
    if not user.stripe_customer_id:
        customer_id = await stripe_service.get_or_create_customer(user)
        user.stripe_customer_id = customer_id
        await db.commit()

    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(user: User = Depends(get_current_user)):
    """Opret Stripe Customer Portal session — administrer abonnement og fakturaer."""
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe er ikke konfigureret.")

    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="Du har intet aktivt abonnement. Opret et abonnement først.",
        )

    try:
        url = await stripe_service.create_portal_session(user)
    except Exception as exc:
        logger.error("Stripe portal fejl: %s", exc)
        raise HTTPException(status_code=503, detail="Stripe fejl — prøv igen")

    return PortalResponse(url=url)


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe webhook — modtager betalings- og abonnementshændelser.

    Verificerer Stripe-signatur og opdaterer brugerens abonnementsstatus.
    Stripe kalder denne endpoint ved:
      - checkout.session.completed
      - customer.subscription.updated
      - customer.subscription.deleted
      - invoice.payment_failed
    """
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook secret ikke konfigureret")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.construct_webhook_event(payload, sig_header)
    except Exception as exc:
        logger.warning("Stripe webhook signatur ugyldig: %s", exc)
        raise HTTPException(status_code=400, detail="Ugyldig webhook-signatur")

    await _handle_stripe_event(event, db)
    return {"received": True}


async def _handle_stripe_event(event, db: AsyncSession) -> None:
    """Håndtér et verificeret Stripe webhook-event."""
    from sqlalchemy import select

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        user_id = data.get("metadata", {}).get("user_id")
        plan = data.get("metadata", {}).get("plan", "starter")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")

        if not user_id:
            return

        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return

        user.stripe_customer_id = customer_id
        user.stripe_subscription_id = subscription_id
        user.plan = plan
        user.subscription_status = "trialing"
        user.trial_ends_at = None
        await db.commit()
        logger.info("Bruger %s opgraderet til %s (checkout.session.completed)", user_id, plan)

    elif event_type == "customer.subscription.updated":
        subscription_id = data.get("id")
        status = data.get("status")  # active | trialing | past_due | canceled
        price_id = None

        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")

        plan = stripe_service.get_plan_from_price_id(price_id) if price_id else None

        result = await db.execute(
            select(User).where(User.stripe_subscription_id == subscription_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return

        if plan:
            user.plan = plan
        user.subscription_status = status

        # Sæt trial/subscription slut-tidspunkt
        trial_end = data.get("trial_end")
        if trial_end:
            user.trial_ends_at = datetime.fromtimestamp(trial_end, tz=timezone.utc)

        current_period_end = data.get("current_period_end")
        if current_period_end:
            user.subscription_ends_at = datetime.fromtimestamp(current_period_end, tz=timezone.utc)

        await db.commit()
        logger.info("Abonnement %s opdateret: %s / %s", subscription_id, status, plan)

    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")

        result = await db.execute(
            select(User).where(User.stripe_subscription_id == subscription_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return

        user.plan = "free"
        user.subscription_status = "canceled"
        user.stripe_subscription_id = None
        await db.commit()
        logger.info("Abonnement %s annulleret — bruger sat til free", subscription_id)

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")

        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return

        user.subscription_status = "past_due"
        await db.commit()
        logger.warning("Betaling fejlet for customer %s", customer_id)
