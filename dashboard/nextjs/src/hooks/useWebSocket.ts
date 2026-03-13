'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { WSEvent } from '@/types';

export function useWebSocket(onMessage: (event: WSEvent) => void) {
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectMsRef = useRef(1000);
  const onMessageRef = useRef(onMessage);

  // Keep callback ref fresh
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectMsRef.current = 1000;
      setConnected(true);
      ws.send(JSON.stringify({ type: 'ping' }));
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as WSEvent;
        if ((data as Record<string, unknown>).type === 'pong') return;
        onMessageRef.current(data);
      } catch (err) {
        console.error('WebSocket parse error', err);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      socketRef.current = null;
      setTimeout(connect, reconnectMsRef.current);
      reconnectMsRef.current = Math.min(reconnectMsRef.current * 2, 30000);
    };

    ws.onerror = () => {
      ws.close();
    };

    socketRef.current = ws;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      socketRef.current?.close();
    };
  }, [connect]);

  return { connected };
}
