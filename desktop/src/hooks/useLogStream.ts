import { useCallback, useEffect, useRef, useState } from "react";
import { currentToken, getWsUrl } from "../api/connection";
import type { LogEntry } from "../api/types";

/**
 * Ring-buffer cap. PLAN.md 6.2 calls out that the web viewer renders every line
 * and that this is a memory problem at scale; the desktop viewer both caps the
 * buffer here and virtualizes the rendering (see `screens/Logs.tsx`).
 */
export const LOG_BUFFER_LIMIT = 10_000;

export interface NormalizedLog {
  id: number;
  ts: string;
  level: string;
  logger: string;
  message: string;
  /** Sidecar stdout/stderr is merged into the same view but rendered apart. */
  source: "backend" | "sidecar";
}

let logSeq = 0;

function normalize(entry: LogEntry): NormalizedLog {
  return {
    id: ++logSeq,
    // The REST snapshot uses `timestamp`, the socket stream uses `ts`.
    ts: entry.ts ?? entry.timestamp ?? new Date().toISOString(),
    level: (entry.level || "INFO").toUpperCase(),
    logger: entry.logger ?? "",
    message: entry.message ?? "",
    source: "backend",
  };
}

/**
 * `/ws/logs` client — one-directional, the server pushes `LogEntry` objects.
 * Ported from `web/src/hooks/useLogStream.ts` with bearer auth and the cap.
 */
export function useLogStream() {
  const [logs, setLogs] = useState<NormalizedLog[]>([]);
  const [connected, setConnected] = useState(false);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedRef = useRef(false);

  const append = useCallback((entry: NormalizedLog) => {
    setLogs((prev) => {
      const next = prev.length >= LOG_BUFFER_LIMIT ? prev.slice(-LOG_BUFFER_LIMIT + 1) : prev;
      return [...next, entry];
    });
  }, []);

  const connect = useCallback(() => {
    if (closedRef.current) return;
    const ws = new WebSocket(getWsUrl("/ws/logs", currentToken()));
    socketRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = (event) => {
      setConnected(false);
      if (event.code === 1008 || closedRef.current) return;
      retryRef.current = setTimeout(connect, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (event) => {
      try {
        append(normalize(JSON.parse(event.data as string) as LogEntry));
      } catch {
        // A malformed frame is not worth tearing the stream down for.
      }
    };
  }, [append]);

  useEffect(() => {
    closedRef.current = false;
    connect();
    return () => {
      closedRef.current = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  const clear = useCallback(() => setLogs([]), []);

  /** Seed the view with the REST snapshot so it is not empty on first paint. */
  const seed = useCallback((entries: LogEntry[]) => {
    setLogs(entries.map(normalize));
  }, []);

  /** Integration point for Rust `backend://stdout` events (sidecar mode, M6). */
  const appendSidecar = useCallback(
    (line: string, level = "INFO") => {
      append({
        id: ++logSeq,
        ts: new Date().toISOString(),
        level,
        logger: "sidecar",
        message: line,
        source: "sidecar",
      });
    },
    [append],
  );

  return { logs, connected, clear, seed, appendSidecar };
}
