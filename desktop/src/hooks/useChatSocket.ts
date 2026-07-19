import { useCallback, useEffect, useRef, useState } from "react";
import { currentToken, getWsUrl } from "../api/connection";

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

let idSeq = 0;
const nextId = () => `m${Date.now()}-${++idSeq}`;

/**
 * `/ws/chat` client — ported from `web/src/hooks/useChatSocket.ts`.
 *
 * Two desktop-specific changes:
 *   1. The URL is derived from the configured backend origin and carries
 *      `?token=`, since the webview has no same-origin cookie (PLAN.md 3.5).
 *   2. Close code 1008 (auth rejected) stops the reconnect loop and is surfaced
 *      via `authFailed` — retrying every 2s with a token the server already
 *      refused just spins.
 */
export function useChatSocket(sessionId: string, initialMessages: ChatMessage[] = []) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [status, setStatus] = useState<ChatStatus>("connecting");
  const [thinking, setThinking] = useState(false);
  const [confirmation, setConfirmation] = useState<ConfirmationRequest | null>(null);
  const [authFailed, setAuthFailed] = useState(false);
  // Live events for the in-flight response — exposed as STATE so the UI shows
  // tool calls happening in real time, not just after the answer arrives.
  const [liveEvents, setLiveEvents] = useState<AgentEvent[]>([]);

  const pendingEvents = useRef<AgentEvent[]>([]);
  const thinkingElapsed = useRef<number | undefined>(undefined);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedRef = useRef(false);
  const sessionIdRef = useRef(sessionId);
  const initialRef = useRef(initialMessages);
  initialRef.current = initialMessages;

  // Switching conversations resets the transcript but keeps the socket: the
  // session id travels per-message, not per-connection.
  useEffect(() => {
    sessionIdRef.current = sessionId;
    setMessages(initialRef.current);
    setThinking(false);
    pendingEvents.current = [];
    setLiveEvents([]);
  }, [sessionId]);

  const connect = useCallback(() => {
    if (closedRef.current) return;
    const ws = new WebSocket(getWsUrl("/ws/chat", currentToken()));
    socketRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      setStatus("open");
      setAuthFailed(false);
    };

    ws.onclose = (event) => {
      setStatus("closed");
      // 1008 = auth rejected (src/dax/web/routes/chat.py). Reconnecting with the
      // same credential cannot succeed, so stop and let the UI say so.
      if (event.code === 1008) {
        setAuthFailed(true);
        return;
      }
      if (!closedRef.current) retryRef.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (event) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(event.data as string) as Record<string, unknown>;
      } catch {
        return;
      }

      if (data.type === "tool_confirmation_request") {
        setConfirmation(data as unknown as ConfirmationRequest);
        return;
      }

      if (data.type === "agent_event") {
        const ev = data.event as AgentEvent;
        if (ev.type === "thinking") {
          setThinking(true);
        } else if (ev.type === "done") {
          thinkingElapsed.current = ev.elapsed_s;
        } else {
          pendingEvents.current = [...pendingEvents.current, ev];
          setLiveEvents(pendingEvents.current);
        }
        return;
      }

      if (
        data.type === "message" &&
        data.role === "assistant" &&
        typeof data.content === "string"
      ) {
        const events = [...pendingEvents.current];
        const elapsed = thinkingElapsed.current;
        pendingEvents.current = [];
        thinkingElapsed.current = undefined;
        setThinking(false);
        setLiveEvents([]);
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: "assistant",
            content: data.content as string,
            timestamp: (data.timestamp as string) ?? new Date().toISOString(),
            agentEvents: events.length > 0 ? events : undefined,
            thinkingElapsed: elapsed,
          },
        ]);
        return;
      }

      // Legacy frame with no `type` field — still emitted by older paths.
      if (!data.type && data.role === "assistant" && typeof data.content === "string") {
        setThinking(false);
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: "assistant",
            content: data.content as string,
            timestamp: (data.timestamp as string) ?? new Date().toISOString(),
          },
        ]);
      }
    };
  }, []);

  useEffect(() => {
    closedRef.current = false;
    connect();
    return () => {
      closedRef.current = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((content: string) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    pendingEvents.current = [];
    thinkingElapsed.current = undefined;
    setLiveEvents([]);
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content, timestamp: new Date().toISOString() },
    ]);
    setThinking(true);
    ws.send(
      JSON.stringify({ content, language: "auto", session_id: sessionIdRef.current }),
    );
  }, []);

  const respondConfirmation = useCallback((approvalId: string, decision: string) => {
    socketRef.current?.send(
      JSON.stringify({ type: "tool_confirmation", approval_id: approvalId, decision }),
    );
    setConfirmation(null);
  }, []);

  /**
   * Drop the modal without answering — used when the countdown reaches zero.
   * The backend has already denied by then (`ApprovalManager` fail-safe), so
   * sending a late decision would be meaningless.
   */
  const expireConfirmation = useCallback(() => setConfirmation(null), []);

  return {
    messages,
    status,
    authFailed,
    thinking,
    liveEvents,
    confirmation,
    send,
    respondConfirmation,
    expireConfirmation,
  };
}
