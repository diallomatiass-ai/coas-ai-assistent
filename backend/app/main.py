from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
import app.models  # noqa: F401 — ensure all models are registered


async def ensure_columns(engine):
    """Tilføj manglende kolonner til eksisterende tabeller."""
    stmts = [
        "ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id)",
        "ALTER TABLE email_messages ADD COLUMN IF NOT EXISTS is_outgoing BOOLEAN DEFAULT false",
        "ALTER TABLE secretary_calls ADD COLUMN IF NOT EXISTS customer_id UUID REFERENCES customers(id)",
        "ALTER TABLE secretary_calls ADD COLUMN IF NOT EXISTS confirmation_sent_at TIMESTAMPTZ",
        "ALTER TABLE ai_secretaries ADD COLUMN IF NOT EXISTS confirmation_enabled BOOLEAN DEFAULT false",
        "ALTER TABLE ai_secretaries ADD COLUMN IF NOT EXISTS confirmation_template TEXT",
        "ALTER TABLE ai_secretaries ADD COLUMN IF NOT EXISTS response_deadline_hours INTEGER DEFAULT 24",
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
    yield
    await engine.dispose()


app = FastAPI(
    title="AI Mailbot",
    description="GDPR-venlig AI-mailbot til danske SMV'er",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.get("/api/health")
async def health():
    return {"status": "ok"}
