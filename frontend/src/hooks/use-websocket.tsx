import { useState, useEffect, useCallback, useRef } from 'react';
import { API_CONFIG } from '@/api/config';

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'failed';

interface UseWebSocketOptions {
  url?: string;
  onMessage?: (data: any) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  maxRetries?: number;
  enabled?: boolean;
}

interface UseWebSocketReturn {
  status: ConnectionStatus;
  reconnect: () => void;
  lastMessage: any | null;
  retryCount: number;
  nextRetryIn: number | null;
}

// Exponential backoff: 5s, 10s, 20s, 40s, max 60s
const getRetryDelay = (retryCount: number): number => {
  const baseDelay = 5000;
  const delay = baseDelay * Math.pow(2, retryCount);
  return Math.min(delay, 60000);
};

export const useWebSocket = (options: UseWebSocketOptions = {}): UseWebSocketReturn => {
  const {
    url = API_CONFIG.wsUrl,
    onMessage,
    onConnect,
    onDisconnect,
    maxRetries = 10,
    enabled = true,
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [lastMessage, setLastMessage] = useState<any | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [nextRetryIn, setNextRetryIn] = useState<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const cleanup = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    if (countdownRef.current) {
      clearInterval(countdownRef.current);
      countdownRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!enabled) return;

    cleanup();
    setStatus('connecting');

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        setRetryCount(0);
        setNextRetryIn(null);
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
          onMessage?.(data);
        } catch {
          // Non-JSON message
          setLastMessage(event.data);
          onMessage?.(event.data);
        }
      };

      ws.onclose = () => {
        setStatus('reconnecting');
        onDisconnect?.();
        scheduleReconnect();
      };

      ws.onerror = () => {
        // onclose will fire after onerror, which handles reconnection
      };
    } catch {
      setStatus('failed');
      scheduleReconnect();
    }
  }, [enabled, url, onConnect, onDisconnect, onMessage, cleanup]); // eslint-disable-line react-hooks/exhaustive-deps

  const scheduleReconnect = useCallback(() => {
    if (retryCount >= maxRetries) {
      setStatus('failed');
      return;
    }

    const delay = getRetryDelay(retryCount);
    setStatus('reconnecting');
    setNextRetryIn(Math.ceil(delay / 1000));

    // Countdown timer
    countdownRef.current = setInterval(() => {
      setNextRetryIn(prev => {
        if (prev === null || prev <= 1) {
          if (countdownRef.current) clearInterval(countdownRef.current);
          return null;
        }
        return prev - 1;
      });
    }, 1000);

    retryTimeoutRef.current = setTimeout(() => {
      setRetryCount(prev => prev + 1);
      connect();
    }, delay);
  }, [retryCount, maxRetries, connect]);

  const reconnect = useCallback(() => {
    cleanup();
    setRetryCount(0);
    setNextRetryIn(null);
    connect();
  }, [connect, cleanup]);

  // Initial connection
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      cleanup();
    };
  }, [enabled]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    status,
    reconnect,
    lastMessage,
    retryCount,
    nextRetryIn,
  };
};
