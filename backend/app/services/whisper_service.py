"""Whisper transskription — tale til tekst via OpenAI Whisper API.

Whisper-1 er exceptionelt god til dansk tale, støj, accenter og dialekter.
Bruges til at transskribere opkald fra AI Sekretæren.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import os

from app.config import settings

logger = logging.getLogger(__name__)


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav", language: str = "da") -> str:
    """Transskribér audio-bytes til tekst via OpenAI Whisper API.

    Args:
        audio_bytes: Rå lydfil-bytes (wav, mp3, m4a, ogg, webm).
        filename:    Filnavn inkl. extension (bruges til MIME-type).
        language:    ISO 639-1 sprogkode — 'da' for dansk.

    Returns:
        Transskriberet tekst.

    Raises:
        RuntimeError: Hvis Whisper API fejler eller API-nøgle mangler.
    """
    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY mangler i .env — nødvendig til Whisper transskription"
        )

    def _do_transcribe() -> str:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)

        # Skriv bytes til temp-fil (Whisper SDK kræver en fil-lignende objekt)
        suffix = os.path.splitext(filename)[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(
                    model=settings.whisper_model,
                    file=f,
                    language=language,
                    response_format="text",
                )
            return result if isinstance(result, str) else result.text
        finally:
            os.unlink(tmp_path)

    try:
        text = await asyncio.to_thread(_do_transcribe)
        logger.info("Whisper transskription: %d tegn", len(text))
        return text.strip()
    except Exception as exc:
        logger.error("Whisper transskription fejlede: %s", exc)
        raise RuntimeError(f"Whisper fejlede: {exc}") from exc


async def analyze_call_sentiment(transcript: str, summary: str) -> dict:
    """Analysér sentiment og tone i et opkald via Claude.

    Returnerer:
        sentiment:   'positiv' | 'neutral' | 'negativ' | 'frustreret'
        urgency_hint: 'high' | 'medium' | 'low'
        key_topics:  Liste af emner nævnt i opkaldet
        action_needed: bool — kræver opkaldet opfølgning?
        confidence:  0.0 – 1.0
    """
    from app.services.ai_engine import _call_claude_async

    prompt = (
        "Du er en dansk samtaleanlyse-ekspert. Analysér dette opkald og returnér KUN gyldig JSON.\n\n"
        f"SAMMENFATNING:\n{summary}\n\n"
        f"TRANSSKRIPTION (uddrag):\n{transcript[:1500]}\n\n"
        "Returnér JSON med disse felter:\n"
        '{"sentiment": "positiv|neutral|negativ|frustreret", '
        '"urgency_hint": "high|medium|low", '
        '"key_topics": ["emne1", "emne2"], '
        '"action_needed": true|false, '
        '"confidence": 0.85}'
    )

    try:
        raw = await _call_claude_async(prompt, model=settings.claude_fast_model, max_tokens=200)

        import json
        text = raw.strip()
        if text.startswith("```"):
            lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        data = json.loads(text)

        valid_sentiments = {"positiv", "neutral", "negativ", "frustreret"}
        valid_urgencies = {"high", "medium", "low"}

        return {
            "sentiment": data.get("sentiment", "neutral") if data.get("sentiment") in valid_sentiments else "neutral",
            "urgency_hint": data.get("urgency_hint", "medium") if data.get("urgency_hint") in valid_urgencies else "medium",
            "key_topics": data.get("key_topics", [])[:5],
            "action_needed": bool(data.get("action_needed", False)),
            "confidence": max(0.0, min(1.0, float(data.get("confidence", 0.7)))),
        }
    except Exception as exc:
        logger.warning("Sentiment-analyse fejlede: %s", exc)
        return {
            "sentiment": "neutral",
            "urgency_hint": "medium",
            "key_topics": [],
            "action_needed": False,
            "confidence": 0.0,
        }
