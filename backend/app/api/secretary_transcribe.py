"""Transskription og sentiment-analyse endpoints til AI Sekretæren."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.secretary_call import SecretaryCall
from app.utils.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class TranscribeResponse(BaseModel):
    transcript: str
    char_count: int
    language: str


class SentimentResponse(BaseModel):
    sentiment: str
    urgency_hint: str
    key_topics: list[str]
    action_needed: bool
    confidence: float


class CallAnalysisResponse(BaseModel):
    call_id: str
    transcript: str | None
    sentiment: str
    urgency_hint: str
    key_topics: list[str]
    action_needed: bool


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(..., description="Lydfil (wav/mp3/m4a/ogg/webm)"),
    language: str = Query("da", description="Sprogkode: da/en/sv/no"),
    user: User = Depends(get_current_user),
):
    """Transskribér en lydfil til tekst via OpenAI Whisper.

    Understøttede formater: wav, mp3, m4a, ogg, webm (maks 25 MB).
    """
    MAX_SIZE = 25 * 1024 * 1024  # 25 MB

    audio_bytes = await file.read()
    if len(audio_bytes) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Lydfil for stor — maks 25 MB")

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Tom lydfil")

    from app.services.whisper_service import transcribe_audio as _transcribe

    try:
        transcript = await _transcribe(
            audio_bytes,
            filename=file.filename or "audio.wav",
            language=language,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return TranscribeResponse(
        transcript=transcript,
        char_count=len(transcript),
        language=language,
    )


@router.post("/calls/{call_id}/analyze", response_model=CallAnalysisResponse)
async def analyze_call(
    call_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kør sentiment-analyse på et eksisterende opkald via Claude.

    Analyserer transskription + sammenfatning og returnerer:
    sentiment, urgency, emner og om opfølgning er nødvendig.
    """
    result = await db.execute(
        select(SecretaryCall).where(SecretaryCall.id == call_id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Opkald ikke fundet")

    if not call.transcript and not call.summary:
        raise HTTPException(status_code=400, detail="Opkaldet har ingen transskription eller sammenfatning")

    from app.services.whisper_service import analyze_call_sentiment

    sentiment_data = await analyze_call_sentiment(
        transcript=call.transcript or "",
        summary=call.summary or "",
    )

    return CallAnalysisResponse(
        call_id=str(call_id),
        transcript=call.transcript,
        **sentiment_data,
    )


@router.get("/calls/{call_id}/transcript")
async def get_call_transcript(
    call_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hent transskription for et opkald."""
    result = await db.execute(
        select(SecretaryCall).where(SecretaryCall.id == call_id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Opkald ikke fundet")

    return {
        "call_id": str(call_id),
        "transcript": call.transcript or "",
        "summary": call.summary or "",
        "caller_name": call.caller_name,
        "caller_phone": call.caller_phone,
        "called_at": call.called_at.isoformat() if call.called_at else None,
    }
