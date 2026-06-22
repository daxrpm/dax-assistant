import { useState, useEffect, useRef, type KeyboardEvent } from "react";
import {
  ActionIcon,
  Badge,
  Button,
  Code,
  Group,
  Loader,
  Modal,
  Paper,
  ScrollArea,
  Stack,
  Text,
  TextInput,
} from "@mantine/core";
import { IconSend, IconShieldLock } from "@tabler/icons-react";

const ROLE = {
  USER: "user",
  ASSISTANT: "assistant",
} as const;

type Role = (typeof ROLE)[keyof typeof ROLE];

const WS_STATE = {
  CONNECTING: "connecting",
  CONNECTED: "connected",
  DISCONNECTED: "disconnected",
} as const;

type WsState = (typeof WS_STATE)[keyof typeof WS_STATE];

interface ChatMessage {
  id: string;
  content: string;
  role: Role;
  timestamp: string;
}

interface WsIncomingMessage {
  content: string;
  role: string;
  channel: string;
  language: string;
  timestamp: string;
}

interface ToolConfirmation {
  type: "tool_confirmation_request";
  approval_id: string;
  tool_name: string;
  server_name: string;
  arguments: Record<string, unknown>;
  timeout_seconds: number;
}

const RECONNECT_DELAY_MS = 3000;

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function formatTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function buildWsUrl(): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/chat`;
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [wsState, setWsState] = useState<WsState>(WS_STATE.DISCONNECTED);
  const [isTyping, setIsTyping] = useState(false);
  const [confirmation, setConfirmation] = useState<ToolConfirmation | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const scrollToBottom = () => {
    if (viewportRef.current) {
      viewportRef.current.scrollTo({
        top: viewportRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  };

  const connect = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setWsState(WS_STATE.CONNECTING);
    const ws = new WebSocket(buildWsUrl());

    ws.onopen = () => {
      setWsState(WS_STATE.CONNECTED);
    };

    ws.onmessage = (event: MessageEvent) => {
      const raw = JSON.parse(event.data as string) as
        | WsIncomingMessage
        | ToolConfirmation;

      // A gated tool needs the user's approval before it runs.
      if ((raw as ToolConfirmation).type === "tool_confirmation_request") {
        setConfirmation(raw as ToolConfirmation);
        return;
      }

      const data = raw as WsIncomingMessage;
      const message: ChatMessage = {
        id: generateId(),
        content: data.content,
        role: data.role === ROLE.ASSISTANT ? ROLE.ASSISTANT : ROLE.USER,
        timestamp: data.timestamp || new Date().toISOString(),
      };
      setIsTyping(false);
      setMessages((prev) => [...prev, message]);
    };

    ws.onclose = () => {
      setWsState(WS_STATE.DISCONNECTED);
      wsRef.current = null;
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  };

  const scheduleReconnect = () => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
    }
    reconnectTimerRef.current = setTimeout(() => {
      connect();
    }, RECONNECT_DELAY_MS);
  };

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      wsRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const sendMessage = () => {
    const trimmed = input.trim();
    if (!trimmed || wsRef.current?.readyState !== WebSocket.OPEN) return;

    const userMessage: ChatMessage = {
      id: generateId(),
      content: trimmed,
      role: ROLE.USER,
      timestamp: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsTyping(true);

    wsRef.current.send(
      JSON.stringify({
        content: trimmed,
        language: "auto",
      }),
    );

    inputRef.current?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const respondConfirmation = (approved: boolean) => {
    if (!confirmation) return;
    wsRef.current?.send(
      JSON.stringify({
        type: "tool_confirmation",
        approval_id: confirmation.approval_id,
        approved,
      }),
    );
    setConfirmation(null);
  };

  const connectionBadgeColor =
    wsState === WS_STATE.CONNECTED
      ? "green"
      : wsState === WS_STATE.CONNECTING
        ? "yellow"
        : "red";

  const connectionLabel =
    wsState === WS_STATE.CONNECTED
      ? "Connected"
      : wsState === WS_STATE.CONNECTING
        ? "Connecting..."
        : "Disconnected";

  return (
    <Stack h="100%" gap={0}>
      {/* Header */}
      <Group justify="space-between" px="md" py="xs">
        <Text fw={600} size="lg">
          Chat
        </Text>
        <Badge color={connectionBadgeColor} variant="dot" size="sm">
          {connectionLabel}
        </Badge>
      </Group>

      {/* Messages area */}
      <ScrollArea
        flex={1}
        px="md"
        viewportRef={viewportRef}
        styles={{
          root: { flex: 1, minHeight: 0 },
        }}
      >
        <Stack gap="sm" py="sm">
          {messages.length === 0 && (
            <Text c="dimmed" ta="center" py="xl">
              Send a message to start the conversation.
            </Text>
          )}

          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}

          {isTyping && (
            <Group gap="xs" px="xs">
              <Loader size="xs" type="dots" />
              <Text size="xs" c="dimmed">
                Dax is thinking...
              </Text>
            </Group>
          )}
        </Stack>
      </ScrollArea>

      {/* Input area */}
      <Group px="md" py="sm" gap="sm" style={{ flexShrink: 0 }}>
        <TextInput
          ref={inputRef}
          flex={1}
          placeholder={
            wsState === WS_STATE.CONNECTED
              ? "Type a message..."
              : "Waiting for connection..."
          }
          value={input}
          onChange={(e) => setInput(e.currentTarget.value)}
          onKeyDown={handleKeyDown}
          disabled={wsState !== WS_STATE.CONNECTED}
          size="md"
        />
        <ActionIcon
          size="lg"
          variant="filled"
          color="blue"
          onClick={sendMessage}
          disabled={
            !input.trim() || wsState !== WS_STATE.CONNECTED
          }
          aria-label="Send message"
        >
          <IconSend size={18} />
        </ActionIcon>
      </Group>

      <Modal
        opened={confirmation !== null}
        onClose={() => respondConfirmation(false)}
        title={
          <Group gap="xs">
            <IconShieldLock size={18} />
            <Text fw={600}>Confirm action</Text>
          </Group>
        }
        centered
      >
        {confirmation && (
          <Stack gap="sm">
            <Text size="sm">
              Dax wants to run{" "}
              <Code>{confirmation.tool_name}</Code>
              {confirmation.server_name ? (
                <>
                  {" "}
                  on <Code>{confirmation.server_name}</Code>
                </>
              ) : null}
              . Allow it?
            </Text>
            <Code block>
              {JSON.stringify(confirmation.arguments, null, 2)}
            </Code>
            <Group justify="flex-end" mt="xs">
              <Button variant="default" onClick={() => respondConfirmation(false)}>
                Deny
              </Button>
              <Button color="blue" onClick={() => respondConfirmation(true)}>
                Allow
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === ROLE.USER;

  return (
    <Group justify={isUser ? "flex-end" : "flex-start"} w="100%">
      <Paper
        p="sm"
        radius="md"
        maw="75%"
        withBorder={!isUser}
        bg={isUser ? "blue.6" : undefined}
        c={isUser ? "white" : undefined}
      >
        <Text size="sm" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
          {message.content}
        </Text>
        <Text
          size="xs"
          c={isUser ? "blue.1" : "dimmed"}
          ta={isUser ? "right" : "left"}
          mt={4}
        >
          {formatTime(message.timestamp)}
        </Text>
      </Paper>
    </Group>
  );
}
