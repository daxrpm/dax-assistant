import { useSyncExternalStore } from "react";
import { currentToken, getWsUrl } from "../api/connection";
import type { LogEntry } from "../api/types";
import { DemandLifecycle } from "../stores/demandLifecycle";

export const LOG_BUFFER_LIMIT = 10_000;

export interface NormalizedLog {
  id: number;
  ts: string;
  level: string;
  logger: string;
  message: string;
  source: "backend" | "sidecar";
}

let logSeq = 0;

function normalize(entry: LogEntry): NormalizedLog {
  return {
    id: ++logSeq,
    ts: entry.ts ?? entry.timestamp ?? new Date().toISOString(),
    level: (entry.level || "INFO").toUpperCase(),
    logger: entry.logger ?? "",
    message: entry.message ?? "",
    source: "backend",
  };
}

function logKey(entry: Pick<NormalizedLog, "ts" | "level" | "logger" | "message">) {
  return `${entry.ts}\u0000${entry.level}\u0000${entry.logger}\u0000${entry.message}`;
}

export function mergeLogSeed(current: NormalizedLog[], entries: LogEntry[]) {
  const merged = new Map<string, NormalizedLog>();
  for (const entry of entries.map(normalize)) merged.set(logKey(entry), entry);
  for (const entry of current) merged.set(logKey(entry), entry);
  return [...merged.values()].slice(-LOG_BUFFER_LIMIT);
}

interface LogSnapshot {
  logs: NormalizedLog[];
  connected: boolean;
}

export function createLogStore() {
  let snapshot: LogSnapshot = { logs: [], connected: false };
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let connectionTimer: ReturnType<typeof setTimeout> | null = null;
  let flushTimer: ReturnType<typeof setTimeout> | null = null;
  let pending: NormalizedLog[] = [];
  let stopped = true;

  const update = (patch: Partial<LogSnapshot>) => {
    snapshot = { ...snapshot, ...patch };
    lifecycle.emit();
  };
  const flush = () => {
    flushTimer = null;
    if (pending.length === 0) return;
    const next = [...snapshot.logs, ...pending].slice(-LOG_BUFFER_LIMIT);
    pending = [];
    update({ logs: next });
  };
  const append = (entry: NormalizedLog) => {
    pending.push(entry);
    flushTimer ??= setTimeout(flush, 16);
  };
  const connect = () => {
    if (stopped || socket) return;
    const ws = new WebSocket(getWsUrl("/ws/logs", currentToken()));
    socket = ws;
    connectionTimer = setTimeout(() => {
      if (socket === ws) ws.close();
    }, 5_000);
    ws.onopen = () => {
      if (socket !== ws) return;
      if (connectionTimer) clearTimeout(connectionTimer);
      connectionTimer = null;
      update({ connected: true });
    };
    ws.onclose = (event) => {
      if (socket !== ws) return;
      socket = null;
      if (connectionTimer) clearTimeout(connectionTimer);
      connectionTimer = null;
      update({ connected: false });
      if (event.code !== 1008 && !stopped) retry = setTimeout(connect, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (event) => {
      if (socket !== ws) return;
      try {
        append(normalize(JSON.parse(event.data as string) as LogEntry));
      } catch {
        // Ignore malformed frames without tearing down the stream.
      }
    };
  };
  const lifecycle = new DemandLifecycle(
    () => {
      stopped = false;
      connect();
    },
    () => {
      stopped = true;
      if (retry) clearTimeout(retry);
      if (connectionTimer) clearTimeout(connectionTimer);
      if (flushTimer) clearTimeout(flushTimer);
      retry = null;
      connectionTimer = null;
      flushTimer = null;
      pending = [];
      const active = socket;
      socket = null;
      active?.close();
      if (snapshot.connected) update({ connected: false });
    },
    true,
  );

  return {
    subscribe: lifecycle.subscribe,
    getSnapshot: () => snapshot,
    clear: () => {
      pending = [];
      update({ logs: [] });
    },
    seed: (entries: LogEntry[]) => {
      flush();
      update({ logs: mergeLogSeed(snapshot.logs, entries) });
    },
    appendSidecar: (line: string, level = "INFO") => append({
      id: ++logSeq,
      ts: new Date().toISOString(),
      level,
      logger: "sidecar",
      message: line,
      source: "sidecar",
    }),
    shutdown: () => lifecycle.shutdown(),
  };
}

export type LogStore = ReturnType<typeof createLogStore>;
export const logStore = createLogStore();

export function useLogStream() {
  const snapshot = useSyncExternalStore(
    logStore.subscribe,
    logStore.getSnapshot,
    logStore.getSnapshot,
  );
  return {
    ...snapshot,
    clear: logStore.clear,
    seed: logStore.seed,
    appendSidecar: logStore.appendSidecar,
  };
}
