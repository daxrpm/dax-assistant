import { useEffect, useRef, useState, useCallback } from "react";
import { Button } from "@heroui/react";
import {
  Send,
  Sparkles,
  ShieldAlert,
  Plus,
  Trash2,
  MessageSquare,
} from "lucide-react";
import { useChatSocket, type ChatMessage } from "../hooks/useChatSocket";
import { api, type ConversationSummary } from "../api/client";
import { Markdown } from "../components/Markdown";
import { Modal, Badge } from "../components/ui";
import { cn } from "../lib/cn";

function newSessionId() {
  return crypto.randomUUID();
}

function getStoredSessionId(): string {
  return localStorage.getItem("dax_session_id") || newSessionId();
}

function formatRelative(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString();
}

export function ChatPage() {
  const [sessionId, setSessionId] = useState<string>(getStoredSessionId);
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { messages, status, thinking, confirmation, send, respondConfirmation } =
    useChatSocket(sessionId, initialMessages);

  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Persist session ID
  useEffect(() => {
    localStorage.setItem("dax_session_id", sessionId);
  }, [sessionId]);

  // Auto-scroll on new messages
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  const loadConversations = useCallback(() => {
    api.listConversations(50).then(setConversations).catch(() => setConversations([]));
  }, []);

  // Load sidebar conversation list on mount and after each message (to update titles)
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Refresh list a moment after a new user message to capture auto-title
  const lastMessageCount = useRef(messages.length);
  useEffect(() => {
    if (messages.length > lastMessageCount.current) {
      lastMessageCount.current = messages.length;
      const t = setTimeout(loadConversations, 1500);
      return () => clearTimeout(t);
    }
  }, [messages.length, loadConversations]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || status !== "open") return;
    send(text);
    setInput("");
  };

  const startNewChat = () => {
    const id = newSessionId();
    setSessionId(id);
    setInitialMessages([]);
    setActiveConvId(null);
  };

  const openConversation = async (conv: ConversationSummary) => {
    if (conv.session_key === sessionId) return;
    try {
      const detail = await api.getConversation(conv.id);
      const msgs: ChatMessage[] = detail.messages.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
        timestamp: m.timestamp,
      }));
      setInitialMessages(msgs);
      setSessionId(conv.session_key);
      setActiveConvId(conv.id);
    } catch {
      // silently ignore load failure
    }
  };

  const deleteConv = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    setDeletingId(convId);
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      // If we deleted the active session, start fresh
      const deleted = conversations.find((c) => c.id === convId);
      if (deleted?.session_key === sessionId) startNewChat();
    } finally {
      setDeletingId(null);
    }
  };

  // Title for header
  const currentTitle =
    activeConvId
      ? (conversations.find((c) => c.id === activeConvId)?.title ?? "Chat")
      : messages.length > 0
      ? "New conversation"
      : "Chat";

  return (
    <div className="flex h-full">
      {/* ── Conversation sidebar ── */}
      <aside className="flex w-56 shrink-0 flex-col border-r border-separator bg-surface">
        <div className="p-3">
          <Button
            variant="primary"
            size="sm"
            className="w-full"
            onPress={startNewChat}
          >
            <Plus size={15} />
            New chat
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto scroll-slim px-2 pb-3">
          {conversations.length === 0 && (
            <p className="px-2 py-4 text-center text-xs text-muted">No conversations yet</p>
          )}
          {conversations.map((conv) => {
            const isActive = conv.session_key === sessionId;
            return (
              <button
                key={conv.id}
                onClick={() => openConversation(conv)}
                className={cn(
                  "group relative flex w-full flex-col gap-0.5 rounded-xl px-3 py-2.5 text-left transition-colors",
                  isActive
                    ? "bg-accent-soft text-accent-soft-foreground"
                    : "text-foreground hover:bg-surface-secondary",
                )}
              >
                <div className="flex items-start gap-1.5">
                  <MessageSquare
                    size={13}
                    className={cn("mt-0.5 shrink-0", isActive ? "text-accent" : "text-muted")}
                  />
                  <span className="line-clamp-2 text-xs font-medium leading-snug">
                    {conv.title || "New conversation"}
                  </span>
                </div>
                <span className="pl-4 text-[10px] text-muted">
                  {formatRelative(conv.updated_at)}
                </span>
                {/* Delete button — visible on hover */}
                <button
                  onClick={(e) => deleteConv(e, conv.id)}
                  disabled={deletingId === conv.id}
                  className="absolute right-2 top-2 hidden rounded-lg p-1 text-muted hover:text-danger group-hover:flex"
                  aria-label="Delete conversation"
                >
                  <Trash2 size={12} />
                </button>
              </button>
            );
          })}
        </div>
      </aside>

      {/* ── Chat area ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <div className="flex h-12 shrink-0 items-center border-b border-separator px-5">
          <h2 className="truncate text-sm font-semibold text-foreground">{currentTitle}</h2>
        </div>

        {/* Messages */}
        <div
          ref={scrollRef}
          className="min-h-0 flex-1 overflow-y-auto scroll-slim px-5 py-5"
        >
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {messages.length === 0 && !thinking && (
              <div className="mt-16 flex flex-col items-center text-center text-muted">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                  <Sparkles size={22} />
                </div>
                <p className="text-base font-medium text-foreground">
                  How can I help?
                </p>
                <p className="mt-1 text-sm">
                  Ask anything — I can access your Nextcloud, run commands on your PC, and more.
                </p>
              </div>
            )}

            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} />
            ))}

            {thinking && (
              <div className="flex justify-start">
                <div className="flex items-center gap-1.5 rounded-2xl border border-separator bg-surface px-4 py-3">
                  <Dot /> <Dot delay="150ms" /> <Dot delay="300ms" />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Composer */}
        <div className="border-t border-separator px-5 py-3">
          <form
            onSubmit={submit}
            className="mx-auto flex max-w-2xl items-end gap-2"
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit(e);
                }
              }}
              rows={1}
              placeholder={status === "open" ? "Message Dax…" : "Connecting…"}
              disabled={status !== "open"}
              className="max-h-40 min-h-[44px] flex-1 resize-none rounded-2xl border border-separator bg-surface px-4 py-3 text-sm outline-none placeholder:text-muted focus:border-accent focus:ring-2 focus:ring-accent/30 scroll-slim"
            />
            <Button
              type="submit"
              variant="primary"
              isIconOnly
              isDisabled={status !== "open" || !input.trim()}
              className="h-11 w-11 shrink-0"
              aria-label="Send"
            >
              <Send size={17} />
            </Button>
          </form>
          {status !== "open" && (
            <p className="mx-auto mt-1 max-w-2xl text-xs text-warning">
              {status === "connecting" ? "Connecting to Dax…" : "Disconnected — retrying…"}
            </p>
          )}
        </div>
      </div>

      {/* Tool confirmation gate */}
      <Modal
        open={confirmation !== null}
        title={
          <span className="flex items-center gap-2">
            <ShieldAlert size={20} className="text-warning" />
            Confirm action
          </span>
        }
        footer={
          confirmation && (
            <>
              <Button
                variant="tertiary"
                onPress={() => respondConfirmation(confirmation.approval_id, false)}
              >
                Deny
              </Button>
              <Button
                variant="primary"
                onPress={() => respondConfirmation(confirmation.approval_id, true)}
              >
                Approve
              </Button>
            </>
          )
        }
      >
        {confirmation && (
          <div className="flex flex-col gap-3">
            <p className="text-muted">
              Dax wants to run a tool that may change your system. Review and confirm.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Badge color="accent">{confirmation.server_name}</Badge>
              <Badge color="warning">{confirmation.tool_name}</Badge>
            </div>
            <pre className="max-h-48 overflow-auto rounded-xl bg-surface-secondary p-3 text-xs scroll-slim">
              {JSON.stringify(confirmation.arguments, null, 2)}
            </pre>
            <p className="text-xs text-muted">
              Auto-denies in {confirmation.timeout_seconds}s if not answered.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}

function MessageBubble({ message: m }: { message: ChatMessage }) {
  const isUser = m.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="mr-2 mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
          <Sparkles size={13} />
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
          isUser
            ? "bg-accent text-accent-foreground"
            : "border border-separator bg-surface text-foreground",
        )}
      >
        {isUser ? (
          <span className="whitespace-pre-wrap">{m.content}</span>
        ) : (
          <Markdown content={m.content} />
        )}
      </div>
    </div>
  );
}

function Dot({ delay = "0ms" }: { delay?: string }) {
  return (
    <span
      className="h-2 w-2 animate-bounce rounded-full bg-muted"
      style={{ animationDelay: delay }}
    />
  );
}
