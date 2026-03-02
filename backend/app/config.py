import logging
import warnings

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://mailbot:changeme@postgres:5432/mailbot"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # JWT
    secret_key: str = "changeme"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    # Gmail OAuth2
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = ""

    # Outlook OAuth2
    outlook_client_id: str = ""
    outlook_client_secret: str = ""
    outlook_tenant_id: str = "common"
    outlook_redirect_uri: str = ""

    # Claude API (Anthropic)
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"       # Svargenerering + chat
    claude_fast_model: str = "claude-haiku-4-5-20251001"  # Klassificering (hurtig + billig)

    # Ollama (bruges stadig til embeddings — Anthropic har intet embedding-API)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b-instruct"     # Fallback hvis Claude API er nede
    ollama_embed_model: str = "nomic-embed-text"

    # ChromaDB
    chroma_host: str = "chromadb"
    chroma_port: int = 8000

    # Encryption
    encryption_key: str = ""

    # Mail sync
    mail_sync_interval_seconds: int = 60

    # Secretary webhook (service-to-service auth)
    secretary_webhook_key: str = ""

    # Ordrestyring.dk
    ordrestyring_api_key: str = ""
    ordrestyring_default_case_status: str = ""

    # Calendar OAuth2 redirect URIs
    google_calendar_redirect_uri: str = ""
    microsoft_calendar_redirect_uri: str = ""

    # Twilio (for SMS-bekræftelser fra backend)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # OpenAI Whisper (tale → tekst transskription)
    openai_api_key: str = ""
    whisper_model: str = "whisper-1"

    # Stripe (abonnementer + betaling)
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter: str = ""   # Price ID fra Stripe Dashboard
    stripe_price_pro: str = ""
    stripe_price_business: str = ""
    stripe_success_url: str = "http://localhost/billing?success=true"
    stripe_cancel_url: str = "http://localhost/billing?canceled=true"

    @field_validator("secret_key")
    @classmethod
    def warn_weak_secret(cls, v):
        if v in ("changeme", "secret", "password", ""):
            warnings.warn("SIKKERHEDSADVARSEL: secret_key er usikker! Sæt en stærk SECRET_KEY i .env")
        return v

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
