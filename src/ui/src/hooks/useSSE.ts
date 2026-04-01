import { useEffect, useRef, useState, useCallback } from "react";

const RECONNECT_DELAY = 3000;
const MAX_ITEMS = 500;

export interface SSEResult<T> {
  items: T[];
  connected: boolean;
  clear: () => void;
}

export function useSSE<T>(url: string): SSEResult<T> {
  const [items, setItems] = useState<T[]>([]);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => {
      if (mountedRef.current) setConnected(true);
    };

    es.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const parsed = JSON.parse(event.data) as T;
        setItems((prev) => {
          const next = [...prev, parsed];
          return next.length > MAX_ITEMS ? next.slice(-MAX_ITEMS) : next;
        });
      } catch {
        // skip unparseable messages
      }
    };

    es.onerror = () => {
      es.close();
      if (mountedRef.current) {
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
      }
    };
  }, [url]);

  useEffect(() => {
    mountedRef.current = true;
    connect();

    return () => {
      mountedRef.current = false;
      esRef.current?.close();
      clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const clear = useCallback(() => setItems([]), []);

  return { items, connected, clear };
}
