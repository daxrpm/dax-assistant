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
  let stopped = true;

  const update = (patch: Partial<LogSnapshot>) => {
    snapshot = { ...snapshot, ...patch };
    lifecycle.emit();
  };
  const append = (entry: NormalizedLog) => {
    const current = snapshot.logs;
    const kept = current.length >= LOG_BUFFER_LIMIT
      ? current.slice(-LOG_BUFFER_LIMIT + 1)
      : current;
    update({ logs: [...kept, entry] });
  };
  const connect = () => {
    if (stopped || socket) return;
    const ws = new WebSocket(getWsUrl("/ws/logs", currentToken()));
    socket = ws;
    ws.onopen = () => update({ connected: true });
    ws.onclose = (event) => {
      if (socket === ws) socket = null;
      update({ connected: false });
      if (event.code !== 1008 && !stopped) retry = setTimeout(connect, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (event) => {
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
      retry = null;
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
    clear: () => update({ logs: [] }),
    seed: (entries: LogEntry[]) => update({ logs: mergeLogSeed(snapshot.logs, entries) }),
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
