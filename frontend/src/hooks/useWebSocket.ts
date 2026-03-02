'use client';

import { useEffect, useRef, useCallback } from 'react';

export type WsEvent =
  | { type: 'connected'; user_id: string }
  | { type: 'new_email'; count: number; account: string }
  | { type: 'new_suggestion'; email_id: string }
  | { type: 'new_action_item'; id: string }
  | { type: 'ping' };

type WsEventHandler = (event: WsEvent) => void;

/**
 * Hook til WebSocket realtids-notifikationer.
 *
 * Forbinder automatisk ved mount, genforbinder ved disconnect.
 * Sender ping hvert 30. sekund for at holde forbindelsen i live.
 *
 * Eksempel:
 *   useWebSocket((event) => {
 *     if (event.type === 'new_email') refetchEmails();
 *   });
 */
export function useWebSocket(onEvent?: WsEventHandler) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const onEventRef = useRef<WsEventHandler | undefined>(onEvent);

  // Hold callback-ref opdateret uden at genåbne forbindelsen
  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const connect = useCallback(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    // Bestem WS URL baseret på nuværende host
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/api/ws?token=${token}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // Start ping-interval
      if (pingTimer.current) clearInterval(pingTimer.current);
      pingTimer.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 30_000);
    };

    ws.onmessage = (evt) => {
      try {
        const event: WsEvent = JSON.parse(evt.data);
        if (event.type === 'ping') {
          ws.send('ping');
          return;
        }
        onEventRef.current?.(event);
      } catch {
        // Ignorér ugyldige beskeder
      }
    };

    ws.onclose = () => {
      if (pingTimer.current) clearInterval(pingTimer.current);
      // Genforbind efter 5 sekunder
      reconnectTimer.current = setTimeout(connect, 5_000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (pingTimer.current) clearInterval(pingTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
