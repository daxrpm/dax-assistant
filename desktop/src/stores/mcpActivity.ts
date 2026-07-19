import { useSyncExternalStore } from "react";
import type { AgentEvent } from "../hooks/useChatSocket";

interface ActiveRun {
  tool: string;
  server: string;
}

export interface McpActivitySnapshot {
  servers: ReadonlySet<string>;
  tools: ReadonlySet<string>;
}

const runsBySession = new Map<string, ActiveRun[]>();
const subscribers = new Set<() => void>();
let snapshot: McpActivitySnapshot = { servers: new Set(), tools: new Set() };

function publish() {
  const runs = [...runsBySession.values()].flat();
  snapshot = {
    servers: new Set(runs.map((run) => run.server).filter(Boolean)),
    tools: new Set(runs.map((run) => run.tool).filter(Boolean)),
  };
  for (const subscriber of subscribers) subscriber();
}

export function trackMcpActivity(sessionId: string, event: AgentEvent) {
  if (event.type === "done") {
    if (runsBySession.delete(sessionId)) publish();
    return;
  }

  if (event.type === "tool_call" && (event.server || event.tool)) {
    const runs = runsBySession.get(sessionId) ?? [];
    runsBySession.set(sessionId, [
      ...runs,
      { tool: event.tool ?? "", server: event.server ?? "" },
    ]);
    publish();
    return;
  }

  if (event.type !== "tool_result") return;
  const runs = runsBySession.get(sessionId);
  if (!runs?.length) return;
  const index = [...runs].reverse().findIndex(
    (run) => (!event.server || !run.server || run.server === event.server) &&
      (!event.tool || run.tool === event.tool),
  );
  if (index === -1) return;
  const actualIndex = runs.length - 1 - index;
  const next = runs.filter((_, runIndex) => runIndex !== actualIndex);
  if (next.length) runsBySession.set(sessionId, next);
  else runsBySession.delete(sessionId);
  publish();
}

export function clearMcpActivity(sessionId: string) {
  if (runsBySession.delete(sessionId)) publish();
}

export function useMcpActivity(): McpActivitySnapshot {
  return useSyncExternalStore(
    (subscriber) => {
      subscribers.add(subscriber);
      return () => subscribers.delete(subscriber);
    },
    () => snapshot,
    () => snapshot,
  );
}
