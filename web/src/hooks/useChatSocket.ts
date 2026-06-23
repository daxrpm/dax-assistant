import { useCallback, useEffect, useRef, useState } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface ConfirmationRequest {
  approval_id: string;
  tool_name: string;
  server_name: string;
  arguments: Record<string, unknown>;
  timeout_seconds: number;
}

type Status = "connecting" | "open" | "closed";

function wsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/chat`;
}

let idSeq = 0;
const nextId = () => `m${Date.now()}-${++idSeq}`;

export function useChatSocket(sessionId: string, initialMessages: ChatMessage[] = []) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [status, setStatus] = useState<Status>("connecting");
  const [thinking, setThinking] = useState(false);
  const [confirmation, setConfirmation] = useState<ConfirmationRequest | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track sessionId in a ref so the WS callbacks always see the latest value.
  const sessionIdRef = useRef(sessionId);

  // When the session switches, load the new history and reset thinking state.
  useEffect(() => {
    sessionIdRef.current = sessionId;
    setMessages(initialMessages);
    setThinking(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const connect = useCallback(() => {
    const ws = new WebSocket(wsUrl());
    socketRef.current = ws;
    setStatus("connecting");

    ws.onopen = () => setStatus("open");
    ws.onclose = () => {
      setStatus("closed");
      retryRef.current = setTimeout(connect, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (event) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }
      if (data.type === "tool_confirmation_request") {
        setConfirmation(data as unknown as ConfirmationRequest);
        return;
      }
      if (data.role === "assistant" && typeof data.content === "string") {
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
    connect();
    return () => {
      if (retryRef.current) clearTimeout(retryRef.current);
      socketRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((content: string) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content, timestamp: new Date().toISOString() },
    ]);
    setThinking(true);
    ws.send(
      JSON.stringify({ content, language: "auto", session_id: sessionIdRef.current }),
    );
  }, []);

  const respondConfirmation = useCallback((approvalId: string, approved: boolean) => {
    const ws = socketRef.current;
    ws?.send(
      JSON.stringify({ type: "tool_confirmation", approval_id: approvalId, approved }),
    );
    setConfirmation(null);
  }, []);

  return { messages, status, thinking, confirmation, send, respondConfirmation };
}
