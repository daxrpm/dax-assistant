import { useSyncExternalStore } from "react";
import { currentToken, getWsUrl } from "../api/connection";
import { DemandLifecycle } from "../stores/demandLifecycle";
import { clearMcpActivity, trackMcpActivity } from "../stores/mcpActivity";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  agentEvents?: AgentEvent[];
  thinkingElapsed?: number;
}

export interface AgentEvent {
  type: "thinking" | "tool_call" | "tool_result" | "done";
  tool?: string;
  server?: string;
  args?: Record<string, unknown>;
  preview?: string;
  error?: boolean;
  elapsed_s?: number;
}

export interface ConfirmationRequest {
  approval_id: string;
  tool_name: string;
  server_name: string;
  arguments: Record<string, unknown>;
  options: string[];
  timeout_seconds: number;
}

export type ChatStatus = "connecting" | "open" | "closed";

interface ChatSnapshot {
  messages: ChatMessage[];
  status: ChatStatus;
  thinking: boolean;
  confirmation: ConfirmationRequest | null;
  authFailed: boolean;
  liveEvents: AgentEvent[];
}

let idSeq = 0;
const nextId = () => `m${Date.now()}-${++idSeq}`;

export const COMMAND_DECK_SESSION_ID = "dax:command-deck";
export const CHAT_MESSAGE_LIMIT = 500;
export const CHAT_STORE_LIMIT = 32;

export function shouldAcceptChatFrame(
  frame: Record<string, unknown>,
  sessionId: string,
): boolean {
  return frame.session_id === sessionId;
}

const boundMessages = (messages: ChatMessage[]) => messages.slice(-CHAT_MESSAGE_LIMIT);

export function createChatStore(sessionId: string, initialMessages: ChatMessage[] = []) {
  let snapshot: ChatSnapshot = {
    messages: boundMessages(initialMessages),
    status: "connecting",
    thinking: false,
    confirmation: null,
    authFailed: false,
    liveEvents: [],
  };
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let connectionTimer: ReturnType<typeof setTimeout> | null = null;
  let stopped = true;
  let forceStopping = false;
  let pendingEvents: AgentEvent[] = [];
  let thinkingElapsed: number | undefined;

  const update = (patch: Partial<ChatSnapshot>) => {
    snapshot = { ...snapshot, ...patch };
    lifecycle.emit();
  };
  const connect = () => {
    if (stopped || socket) return;
    const ws = new WebSocket(getWsUrl("/ws/chat", currentToken()));
    socket = ws;
    update({ status: "connecting" });
    connectionTimer = setTimeout(() => {
      if (socket === ws) ws.close();
    }, 5_000);
    ws.onopen = () => {
      if (socket !== ws) return;
      if (connectionTimer) clearTimeout(connectionTimer);
      connectionTimer = null;
      update({ status: "open", authFailed: false });
    };
    ws.onclose = (event) => {
      if (socket !== ws) return;
      socket = null;
      clearMcpActivity(sessionId);
      if (connectionTimer) clearTimeout(connectionTimer);
      connectionTimer = null;
      update({ status: "closed", authFailed: event.code === 1008 });
      if (event.code !== 1008 && !stopped) retry = setTimeout(connect, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (event) => {
      if (socket !== ws) return;
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(event.data as string) as Record<string, unknown>;
      } catch {
        return;
      }
      // This socket never changes session, so even legacy untagged frames cannot
      // leak into another conversation when the UI switches routes or threads.
      if (!shouldAcceptChatFrame(data, sessionId)) return;
      if (data.type === "tool_confirmation_request") {
        update({ confirmation: data as unknown as ConfirmationRequest });
      } else if (data.type === "agent_event") {
        const agentEvent = data.event as AgentEvent;
        trackMcpActivity(sessionId, agentEvent);
        if (agentEvent.type === "thinking") {
          update({ thinking: true });
        } else if (agentEvent.type === "done") {
          thinkingElapsed = agentEvent.elapsed_s;
        } else {
          pendingEvents = [...pendingEvents, agentEvent];
          update({ liveEvents: pendingEvents });
        }
      } else if (
        data.role === "assistant" &&
        typeof data.content === "string" &&
        (data.type === "message" || !data.type)
      ) {
        const message: ChatMessage = {
          id: nextId(),
          role: "assistant",
          content: data.content,
          timestamp: (data.timestamp as string) ?? new Date().toISOString(),
        };
        if (data.type === "message" && pendingEvents.length > 0) {
          message.agentEvents = pendingEvents;
        }
        if (data.type === "message" && thinkingElapsed !== undefined) {
          message.thinkingElapsed = thinkingElapsed;
        }
        pendingEvents = [];
        thinkingElapsed = undefined;
        clearMcpActivity(sessionId);
        update({
          messages: boundMessages([...snapshot.messages, message]),
          thinking: false,
          liveEvents: [],
        });
        if (!lifecycle.hasSubscribers()) lifecycle.shutdown();
      }
    };
  };
  const lifecycle = new DemandLifecycle(
    () => {
      stopped = false;
      connect();
    },
    () => {
      if (snapshot.thinking && !forceStopping) return;
      stopped = true;
      if (retry) clearTimeout(retry);
      if (connectionTimer) clearTimeout(connectionTimer);
      retry = null;
      connectionTimer = null;
      const active = socket;
      socket = null;
      active?.close();
      clearMcpActivity(sessionId);
      if (snapshot.status !== "closed") update({ status: "closed" });
    },
  );

  return {
    sessionId,
    subscribe: lifecycle.subscribe,
    getSnapshot: () => snapshot,
    send(content: string) {
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      pendingEvents = [];
      thinkingElapsed = undefined;
      update({
        messages: boundMessages([
          ...snapshot.messages,
          { id: nextId(), role: "user", content, timestamp: new Date().toISOString() },
        ]),
        thinking: true,
        liveEvents: [],
      });
      socket.send(JSON.stringify({ content, language: "auto", session_id: sessionId }));
    },
    respondConfirmation(approvalId: string, decision: string) {
      socket?.send(JSON.stringify({
        type: "tool_confirmation",
        approval_id: approvalId,
        decision,
      }));
      update({ confirmation: null });
    },
    expireConfirmation: () => update({ confirmation: null }),
    isActive: () => lifecycle.hasSubscribers(),
    shutdown: () => {
      forceStopping = true;
      lifecycle.shutdown();
      forceStopping = false;
    },
  };
}

export type ChatStore = ReturnType<typeof createChatStore>;
const chatStores = new Map<string, ChatStore>();

export function getChatStore(sessionId: string, initialMessages: ChatMessage[] = []) {
  let store = chatStores.get(sessionId);
  if (!store) {
    if (chatStores.size >= CHAT_STORE_LIMIT) {
      const oldest = [...chatStores.entries()].find(
        ([id, candidate]) => id !== COMMAND_DECK_SESSION_ID && !candidate.isActive(),
      )?.[0];
      if (oldest) {
        chatStores.get(oldest)?.shutdown();
        chatStores.delete(oldest);
      }
    }
    store = createChatStore(sessionId, initialMessages);
    chatStores.set(sessionId, store);
  } else {
    chatStores.delete(sessionId);
    chatStores.set(sessionId, store);
  }
  return store;
}

export function shutdownChatStores() {
  for (const store of chatStores.values()) store.shutdown();
  chatStores.clear();
}

export function useChatSocket(sessionId: string, initialMessages: ChatMessage[] = []) {
  const store = getChatStore(sessionId, initialMessages);
  const snapshot = useSyncExternalStore(
    store.subscribe,
    store.getSnapshot,
    store.getSnapshot,
  );
  return {
    ...snapshot,
    send: store.send,
    respondConfirmation: store.respondConfirmation,
    expireConfirmation: store.expireConfirmation,
  };
}
