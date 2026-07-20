import { useCallback, useEffect, useRef, useState } from "react";

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

type Status = "connecting" | "open" | "closed";

export const CHAT_MESSAGE_LIMIT = 500;
export const CHAT_EVENT_LIMIT = 200;

export const boundChatMessages = (messages: ChatMessage[]) =>
  messages.slice(-CHAT_MESSAGE_LIMIT);

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/chat`;
}

let idSeq = 0;
const nextId = () => `m${Date.now()}-${++idSeq}`;

export function shouldAcceptChatFrame(
  frame: Record<string, unknown>,
  sessionId: string,
): boolean {
  return frame.session_id === sessionId;
}

export function useChatSocket(sessionId: string, initialMessages: ChatMessage[] = []) {
  const [messages, setMessages] = useState<ChatMessage[]>(boundChatMessages(initialMessages));
  const [status, setStatus] = useState<Status>("connecting");
  const [authFailed, setAuthFailed] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [confirmation, setConfirmation] = useState<ConfirmationRequest | null>(null);
  // Live events for the in-flight response — exposed as STATE so the UI shows
  // tool calls happening in real time (not just after the answer arrives).
  const [liveEvents, setLiveEvents] = useState<AgentEvent[]>([]);
  const pendingEvents = useRef<AgentEvent[]>([]);
  const thinkingElapsed = useRef<number | undefined>(undefined);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionIdRef = useRef(sessionId);
  const shouldReconnectRef = useRef(false);

  useEffect(() => {
    const previousSessionId = sessionIdRef.current;
    sessionIdRef.current = sessionId;
    const ws = socketRef.current;
    if (previousSessionId !== sessionId && ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: "session_unsubscribe",
        session_ids: [previousSessionId],
      }));
      ws.send(JSON.stringify({ type: "session_subscribe", session_ids: [sessionId] }));
    }
    setMessages(boundChatMessages(initialMessages));
    setThinking(false);
    pendingEvents.current = [];
    setLiveEvents([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl());
    socketRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => {
      if (socketRef.current !== ws) return;
      ws.send(JSON.stringify({
        type: "session_subscribe",
        session_ids: [sessionIdRef.current],
      }));
      setStatus("open");
      setAuthFailed(false);
    };
    ws.onclose = (event) => {
      if (socketRef.current !== ws) return;
      socketRef.current = null;
      setStatus("closed");
      setAuthFailed(event.code === 1008);
      if (event.code !== 1008 && shouldReconnectRef.current) {
        retryRef.current = setTimeout(connect, 2000);
      }
    };
    ws.onerror = () => ws.close();

    ws.onmessage = (event) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }
      if (!shouldAcceptChatFrame(data, sessionIdRef.current)) return;

      // Tool confirmation modal
      if (data.type === "tool_confirmation_request") {
        setConfirmation(data as unknown as ConfirmationRequest);
        return;
      }

      // Agent streaming events
      if (data.type === "agent_event") {
        const ev = data.event as AgentEvent;
        if (ev.type === "thinking") {
          setThinking(true);
        } else if (ev.type === "done") {
          thinkingElapsed.current = ev.elapsed_s;
        } else {
          pendingEvents.current = [...pendingEvents.current, ev].slice(-CHAT_EVENT_LIMIT);
          setLiveEvents(pendingEvents.current); // live update for the UI
        }
        return;
      }

      // Final assistant message
      if (data.type === "message" && data.role === "assistant" && typeof data.content === "string") {
        const events = [...pendingEvents.current];
        const elapsed = thinkingElapsed.current;
        pendingEvents.current = [];
        thinkingElapsed.current = undefined;
        setThinking(false);
        setLiveEvents([]);
        setMessages((prev) => boundChatMessages([
          ...prev,
          {
            id: nextId(),
            role: "assistant",
            content: data.content as string,
            timestamp: (data.timestamp as string) ?? new Date().toISOString(),
            agentEvents: events.length > 0 ? events : undefined,
            thinkingElapsed: elapsed,
          },
        ]));
        return;
      }

      // Legacy format (no type field) — backward compat
      if (!data.type && data.role === "assistant" && typeof data.content === "string") {
        setThinking(false);
        setMessages((prev) => boundChatMessages([
          ...prev,
          {
            id: nextId(),
            role: "assistant",
            content: data.content as string,
            timestamp: (data.timestamp as string) ?? new Date().toISOString(),
          },
        ]));
      }
    };
  }, []);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();
    return () => {
      shouldReconnectRef.current = false;
      if (retryRef.current) clearTimeout(retryRef.current);
      retryRef.current = null;
      const ws = socketRef.current;
      socketRef.current = null;
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "session_unsubscribe",
          session_ids: [sessionIdRef.current],
        }));
      }
      ws?.close();
    };
  }, [connect]);

  const send = useCallback((content: string) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    pendingEvents.current = [];
    thinkingElapsed.current = undefined;
    setLiveEvents([]);
    setMessages((prev) => boundChatMessages([
      ...prev,
      { id: nextId(), role: "user", content, timestamp: new Date().toISOString() },
    ]));
    setThinking(true);
    ws.send(
      JSON.stringify({ content, language: "auto", session_id: sessionIdRef.current }),
    );
  }, []);

  const respondConfirmation = useCallback((approvalId: string, decision: string) => {
    const ws = socketRef.current;
    ws?.send(
      JSON.stringify({ type: "tool_confirmation", approval_id: approvalId, decision }),
    );
    setConfirmation(null);
  }, []);

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
