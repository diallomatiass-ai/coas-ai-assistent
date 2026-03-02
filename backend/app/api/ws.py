"""WebSocket endpoint til realtids-notifikationer.

Arkitektur:
  Celery worker  →  Redis pub/sub (kanal: ws_events)  →  FastAPI baggrundstask  →  WebSocket klienter

Klienter forbinder på /api/ws?token=<JWT>.
Serveren pusher JSON-beskeder ved:
  - Ny email modtaget       (type: "new_email")
  - AI-forslag klar         (type: "new_suggestion")
  - Nyt action item         (type: "new_action_item")
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

REDIS_CHANNEL = "ws_events"

# In-process forbindelsesregister: { user_id (str) -> set[WebSocket] }
_connections: dict[str, set[WebSocket]] = defaultdict(set)


def _get_user_id_from_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None


async def broadcast_to_user(user_id: str, event: dict) -> None:
    """Send JSON-event til alle WebSocket-forbindelser for én bruger."""
    sockets = _connections.get(str(user_id), set())
    if not sockets:
        return
    message = json.dumps(event)
    dead: set[WebSocket] = set()
    for ws in list(sockets):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        sockets.discard(ws)


async def redis_listener() -> None:
    """Baggrundstask: lytter på Redis pub/sub og broadcaster til WebSocket klienter.

    Starter ved FastAPI lifespan og kører kontinuerligt.
    Publiser events via: publish_ws_event(user_id, event_dict)
    """
    import redis.asyncio as aioredis

    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(REDIS_CHANNEL)
    logger.info("WebSocket Redis listener startet på kanal: %s", REDIS_CHANNEL)

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                payload = json.loads(message["data"])
                user_id = payload.get("user_id")
                event = payload.get("event", {})
                if user_id and event:
                    await broadcast_to_user(user_id, event)
            except (json.JSONDecodeError, Exception) as exc:
                logger.warning("WebSocket Redis besked fejl: %s", exc)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(REDIS_CHANNEL)
        await redis_client.aclose()
        logger.info("WebSocket Redis listener stoppet")


def publish_ws_event(user_id: str, event: dict) -> None:
    """Publish et WS-event til Redis (synkron — bruges fra Celery tasks).

    Eksempel:
        publish_ws_event(str(user.id), {"type": "new_email", "count": 3})
    """
    import redis as sync_redis

    r = sync_redis.from_url(settings.redis_url, decode_responses=True)
    payload = json.dumps({"user_id": user_id, "event": event})
    r.publish(REDIS_CHANNEL, payload)
    r.close()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """WebSocket endpoint — forbind med: ws://localhost:8000/api/ws?token=<JWT>"""
    user_id = _get_user_id_from_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Ugyldigt token")
        return

    await websocket.accept()
    _connections[user_id].add(websocket)
    logger.info("WebSocket forbundet — user %s (aktive: %d)", user_id, len(_connections[user_id]))

    await websocket.send_text(json.dumps({"type": "connected", "user_id": user_id}))

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=45.0)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket fejl for user %s: %s", user_id, exc)
    finally:
        _connections[user_id].discard(websocket)
        if not _connections[user_id]:
            _connections.pop(user_id, None)
        logger.info("WebSocket afbrudt — user %s", user_id)
