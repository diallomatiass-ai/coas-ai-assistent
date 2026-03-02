import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.config import settings
from app.database import engine, Base
from app.api.auth import router as auth_router
from app.api.emails import router as emails_router
from app.api.suggestions import router as suggestions_router
from app.api.templates import router as templates_router
from app.api.knowledge import router as knowledge_router
from app.api.webhooks import router as webhooks_router
from app.api.chat import router as chat_router
from app.api.ai_secretary import router as ai_secretary_router
from app.api.customers import router as customers_router
from app.api.action_items import router as action_items_router
from app.api.secretary_webhook import router as secretary_webhook_router
from app.api.reminders import router as reminders_router
from app.api.calendar import router as calendar_router
from app.api.calendar_webhooks import router as calendar_webhooks_router
from app.api.booking_rules import router as booking_rules_router
from app.api.admin import router as admin_router
from app.api.sms import router as sms_router
from app.api.ws import router as ws_router
from app.api.billing import router as billing_router
from app.api.secretary_transcribe import router as transcribe_router
import app.models  # noqa: F401 — ensure all models are registered

# Rate limiter — 10 forespørgsler pr. minut pr. IP på chat + emails
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


async def ensure_columns(engine):
    """Tilføj manglende kolonner og indexes til eksisterende tabeller."""
    stmts = [
        # Kolonner
        "ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id)",
        "ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS is_outgoing BOOLEAN DEFAULT false",
        "ALTER TABLE secretary_calls ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id)",
        "ALTER TABLE secretary_calls ADD COLUMN IF NOT EXISTS confirmation_sent_at TIMESTAMPTZ",
        "ALTER TABLE ai_secretaries ADD COLUMN IF NOT EXISTS confirmation_enabled BOOLEAN DEFAULT false",
        "ALTER TABLE ai_secretaries ADD COLUMN IF NOT EXISTS confirmation_template TEXT",
        "ALTER TABLE ai_secretaries ADD COLUMN IF NOT EXISTS response_deadline_hours INTEGER DEFAULT 24",
        "ALTER TABLE ai_secretaries ADD COLUMN IF NOT EXISTS booking_rules JSONB",
        # Stripe kolonner på users
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255) UNIQUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255) UNIQUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS plan VARCHAR(50) DEFAULT 'free'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'free'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_ends_at TIMESTAMPTZ",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_ends_at TIMESTAMPTZ",
        # Performance indexes
        "CREATE INDEX IF NOT EXISTS idx_email_user_received ON email_messages (account_id, received_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_email_category ON email_messages (account_id, category)",
        "CREATE INDEX IF NOT EXISTS idx_email_is_read ON email_messages (account_id, is_read)",
        "CREATE INDEX IF NOT EXISTS idx_action_items_user_status ON action_items (user_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_action_items_deadline ON action_items (user_id, deadline)",
        "CREATE INDEX IF NOT EXISTS idx_suggestions_email ON ai_suggestions (email_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_mail_accounts_user ON mail_accounts (user_id, is_active)",
        # Fulltekst-søgning: GIN index på subject + body_text
        """CREATE INDEX IF NOT EXISTS idx_email_fulltext ON email_messages
           USING gin(to_tsvector('danish', coalesce(subject,'') || ' ' || coalesce(body_text,'')))""",
    ]
    async with engine.begin() as conn:
        for stmt in stmts:
            await conn.execute(text(stmt))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_columns(engine)

    # Start WebSocket Redis listener som baggrundstask
    from app.api.ws import redis_listener
    ws_task = asyncio.create_task(redis_listener())

    yield

    ws_task.cancel()
    try:
        await ws_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


app = FastAPI(
    title="AI Mailbot",
    description="GDPR-venlig AI-mailbot til danske SMV'er",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:3000", os.getenv("FRONTEND_URL", "http://localhost")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(emails_router, prefix="/api/emails", tags=["emails"])
app.include_router(suggestions_router, prefix="/api/suggestions", tags=["suggestions"])
app.include_router(templates_router, prefix="/api/templates", tags=["templates"])
app.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(chat_router, prefix="/api/chat", tags=["chat"])
app.include_router(ai_secretary_router, prefix="/api/ai-secretary", tags=["ai-secretary"])
app.include_router(customers_router, prefix="/api/customers", tags=["customers"])
app.include_router(action_items_router, prefix="/api/action-items", tags=["action-items"])
app.include_router(secretary_webhook_router, prefix="/api/webhooks", tags=["secretary-webhook"])
app.include_router(reminders_router, prefix="/api/reminders", tags=["reminders"])
app.include_router(calendar_router, prefix="/api/calendar", tags=["calendar"])
app.include_router(calendar_webhooks_router, prefix="/api/calendar/oauth", tags=["calendar-oauth"])
app.include_router(booking_rules_router, prefix="/api/booking-rules", tags=["booking-rules"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(sms_router, prefix="/api/sms", tags=["sms"])
app.include_router(ws_router, prefix="/api", tags=["websocket"])
app.include_router(billing_router, prefix="/api/billing", tags=["billing"])
app.include_router(transcribe_router, prefix="/api/secretary", tags=["secretary-transcribe"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}
