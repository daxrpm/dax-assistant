import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { LogEntry } from "../types/config";

const MAX = 1000;

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/logs`;
}

/** Streams backend logs: seeds from REST history, then live over WebSocket. */
export function useLogStream() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const append = useCallback((entry: LogEntry) => {
    setLogs((prev) => {
      const next = [...prev, entry];
      return next.length > MAX ? next.slice(next.length - MAX) : next;
    });
  }, []);

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl());
    socketRef.current = ws;
    ws.onopen = () => setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      retryRef.current = setTimeout(connect, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (event) => {
      try {
        append(JSON.parse(event.data) as LogEntry);
      } catch {
        /* ignore malformed frames */
      }
    };
  }, [append]);

  useEffect(() => {
    api.getLogs(300).then(setLogs).catch(() => setLogs([]));
    connect();
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  const clear = useCallback(() => setLogs([]), []);

  return { logs, connected, clear };
}
