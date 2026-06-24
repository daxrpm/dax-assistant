import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@heroui/react";
import {
  Send,
  Sparkles,
  ShieldAlert,
  Plus,
  Trash2,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  Activity,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Wrench,
} from "lucide-react";
import { useChatSocket, type ChatMessage, type AgentEvent } from "../hooks/useChatSocket";
import { api, type ConversationSummary } from "../api/client";
import { Markdown } from "../components/Markdown";
import { Modal, Badge } from "../components/ui";
import { cn } from "../lib/cn";

/* ── Helpers ──────────────────────────────────────────────────────────────── */

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
  return days < 7 ? `${days}d ago` : d.toLocaleDateString();
}

/* ── Thinking dots ────────────────────────────────────────────────────────── */

function Dot({ delay = "0ms" }: { delay?: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-current"
      style={{ animationDelay: delay }}
    />
  );
}

/* ── Inline tool event line ───────────────────────────────────────────────── */

function ToolEventLine({ ev }: { ev: AgentEvent }) {
  if (ev.type === "tool_call") {
    const label = ev.server ? `${ev.server} · ${ev.tool}` : ev.tool ?? "";
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted">
        <Loader2 size={11} className="animate-spin text-accent" />
        <span>Calling <span className="font-mono">{label}</span>…</span>
      </div>
    );
  }
  if (ev.type === "tool_result") {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted">
        {ev.error ? (
          <AlertCircle size={11} className="text-danger-soft-foreground" />
        ) : (
          <CheckCircle2 size={11} className="text-success-soft-foreground" />
        )}
        <span className="font-mono">{ev.tool}</span>
        <span>{ev.error ? "error" : "done"}</span>
      </div>
    );
  }
  return null;
}

/* ── Collapsible "Thought for Xs" section ─────────────────────────────────── */

function ThoughtSummary({
  events,
  elapsed,
}: {
  events: AgentEvent[];
  elapsed?: number;
}) {
  const [open, setOpen] = useState(false);
  const toolCalls = events.filter((e) => e.type === "tool_call");
  if (toolCalls.length === 0 && !elapsed) return null;

  const label = elapsed != null ? `Thought for ${elapsed}s` : "Thinking";

  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-muted transition-colors hover:text-foreground"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span>{label}</span>
        {toolCalls.length > 0 && (
          <span className="ml-1 rounded-full bg-surface-secondary px-1.5 py-0.5 font-mono text-[10px]">
            {toolCalls.length} tool{toolCalls.length !== 1 ? "s" : ""}
          </span>
        )}
      </button>
      {open && (
        <div className="mt-1.5 flex flex-col gap-1 rounded-xl border border-separator bg-surface-secondary px-3 py-2">
          {events.map((ev, i) => (
            <ToolEventLine key={i} ev={ev} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Message bubble ───────────────────────────────────────────────────────── */

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-2xl rounded-br-md bg-surface-secondary px-4 py-2.5 text-sm">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
        <Sparkles size={13} />
      </div>
      <div className="min-w-0 flex-1 pt-0.5">
        <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
          <Markdown content={message.content} />
        </div>
        {message.agentEvents && message.agentEvents.length > 0 && (
          <ThoughtSummary events={message.agentEvents} elapsed={message.thinkingElapsed} />
        )}
      </div>
    </div>
  );
}

/* ── Activity panel ───────────────────────────────────────────────────────── */

function ActivityPanel({
  events,
  elapsed,
  onClose,
}: {
  events: AgentEvent[];
  elapsed?: number;
  onClose: () => void;
}) {
  const toolCalls = events.filter((e) => e.type === "tool_call" || e.type === "tool_result");

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-l border-separator bg-surface">
      <div className="flex h-12 items-center justify-between border-b border-separator px-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Activity size={15} />
          Activity
          {elapsed != null && (
            <span className="text-xs font-normal text-muted">· {elapsed}s</span>
          )}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg p-1 text-muted hover:bg-surface-secondary"
        >
          <X size={15} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto scroll-slim p-4">
        {toolCalls.length === 0 ? (
          <p className="text-xs text-muted">No tool activity yet</p>
        ) : (
          <div className="flex flex-col gap-3">
            {toolCalls.map((ev, i) => {
              if (ev.type === "tool_call") {
                return (
                  <div key={i} className="flex flex-col gap-1">
                    <div className="flex items-center gap-1.5 text-xs font-medium">
                      <Wrench size={11} className="text-accent" />
                      <span className="font-mono">{ev.tool}</span>
                    </div>
                    {ev.server && (
                      <span className="ml-4 text-[10px] text-muted">{ev.server}</span>
                    )}
                    {ev.args && Object.keys(ev.args).length > 0 && (
                      <pre className="ml-4 overflow-x-auto rounded-lg bg-surface-secondary p-1.5 font-mono text-[10px] text-muted scroll-slim">
                        {JSON.stringify(ev.args, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              }
              if (ev.type === "tool_result") {
                return (
                  <div key={i} className="flex flex-col gap-1">
                    <div className="flex items-center gap-1.5 text-xs">
                      {ev.error ? (
                        <AlertCircle size={11} className="text-danger-soft-foreground" />
                      ) : (
                        <CheckCircle2 size={11} className="text-success-soft-foreground" />
                      )}
                      <span className="text-muted">{ev.error ? "Error" : "Result"}</span>
                    </div>
                    {ev.preview && (
                      <pre className="ml-4 overflow-x-auto rounded-lg bg-surface-secondary p-1.5 font-mono text-[10px] text-muted scroll-slim">
                        {ev.preview}
                      </pre>
                    )}
                  </div>
                );
              }
              return null;
            })}
          </div>
        )}
      </div>
    </aside>
  );
}

/* ── Model selector ───────────────────────────────────────────────────────── */

const PROVIDERS = ["openai", "anthropic", "gemini", "ollama"] as const;

function ModelSelector({
  provider,
  model,
  onChange,
}: {
  provider: string;
  model: string;
  onChange: (provider: string, model: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [models, setModels] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const loadModels = async () => {
    if (Object.keys(models).length > 0) return;
    setLoading(true);
    try {
      const data = await api.listLLMModels();
      setModels(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const shortModel = model.length > 18 ? model.slice(0, 16) + "…" : model;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => { setOpen((v) => !v); if (!open) loadModels(); }}
        className="flex items-center gap-1.5 rounded-full border border-separator bg-surface px-3 py-1 text-xs text-muted transition-colors hover:border-accent/50 hover:text-foreground"
      >
        <span className="capitalize">{provider}</span>
        <span className="text-muted/50">·</span>
        <span className="font-mono">{shortModel}</span>
        <ChevronDown size={11} />
      </button>

      {open && (
        <div className="absolute bottom-full left-0 z-50 mb-2 w-72 overflow-hidden rounded-xl border border-separator bg-surface shadow-xl">
          {loading ? (
            <div className="flex items-center gap-2 p-3 text-xs text-muted">
              <Loader2 size={12} className="animate-spin" />
              Loading models…
            </div>
          ) : (
            <div className="max-h-72 overflow-y-auto scroll-slim">
              {PROVIDERS.map((prov) => {
                const list = models[prov] ?? [];
                if (list.length === 0) return null;
                return (
                  <div key={prov}>
                    <div className="sticky top-0 bg-surface px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted">
                      {prov}
                    </div>
                    {list.map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => { onChange(prov, m); setOpen(false); }}
                        className={cn(
                          "flex w-full items-center px-3 py-1.5 text-left text-xs transition-colors hover:bg-surface-secondary",
                          prov === provider && m === model
                            ? "text-accent font-medium"
                            : "text-foreground",
                        )}
                      >
                        <span className="font-mono">{m}</span>
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main ChatPage ────────────────────────────────────────────────────────── */

export function ChatPage() {
  const [sessionId, setSessionId] = useState<string>(getStoredSessionId);
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o");

  const { messages, status, thinking, confirmation, send, respondConfirmation } =
    useChatSocket(sessionId, initialMessages);

  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Last message for activity panel
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");

  // Load current provider/model from config
  useEffect(() => {
    api.getConfig().then((cfg) => {
      setProvider(cfg.llm.default_provider);
      const p = cfg.llm.default_provider;
      const m =
        p === "anthropic" ? cfg.llm.anthropic_model :
        p === "openai" ? cfg.llm.openai_model :
        p === "gemini" ? cfg.llm.gemini_model :
        cfg.llm.ollama_model;
      if (m) setModel(m);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    localStorage.setItem("dax_session_id", sessionId);
  }, [sessionId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 160)}px`;
  }, [input]);

  const loadConversations = useCallback(() => {
    api.listConversations(50).then(setConversations).catch(() => setConversations([]));
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);

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
      // silently ignore
    }
  };

  const deleteConv = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    setDeletingId(convId);
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      const deleted = conversations.find((c) => c.id === convId);
      if (deleted?.session_key === sessionId) startNewChat();
    } finally {
      setDeletingId(null);
    }
  };

  const changeModel = async (newProvider: string, newModel: string) => {
    setProvider(newProvider);
    setModel(newModel);
    try {
      const modelKey =
        newProvider === "anthropic" ? "anthropic_model" :
        newProvider === "openai" ? "openai_model" :
        newProvider === "gemini" ? "gemini_model" :
        "ollama_model";
      await api.updateLLM({ default_provider: newProvider, [modelKey]: newModel });
    } catch {
      // ignore — will take effect on next reload anyway
    }
  };

  const currentTitle =
    activeConvId
      ? (conversations.find((c) => c.id === activeConvId)?.title ?? "Chat")
      : messages.length > 0 ? "New conversation" : "Chat";

  return (
    <div className="flex h-full">
      {/* ── Conversation sidebar ───────────────────────────────────────────── */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-separator bg-surface">
        {/* New chat */}
        <div className="p-3">
          <Button variant="ghost" size="sm" className="w-full justify-start gap-2" onPress={startNewChat}>
            <Plus size={15} />
            New chat
          </Button>
        </div>

        <div className="mx-3 mb-2 border-t border-separator" />

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto scroll-slim px-2 pb-3">
          {conversations.length === 0 && (
            <p className="px-3 py-4 text-center text-xs text-muted">No conversations yet</p>
          )}
          {conversations.map((conv) => {
            const isActive = conv.session_key === sessionId;
            return (
              <button
                key={conv.id}
                onClick={() => openConversation(conv)}
                className={cn(
                  "group relative flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left transition-colors",
                  isActive
                    ? "bg-accent-soft text-accent-soft-foreground"
                    : "text-foreground hover:bg-surface-secondary",
                )}
              >
                <MessageSquare
                  size={14}
                  className={cn("shrink-0", isActive ? "text-accent" : "text-muted")}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium">
                    {conv.title || "New conversation"}
                  </p>
                  <p className="text-[10px] text-muted">{formatRelative(conv.updated_at)}</p>
                </div>
                <button
                  onClick={(e) => deleteConv(e, conv.id)}
                  disabled={deletingId === conv.id}
                  className="hidden rounded-md p-0.5 text-muted hover:text-danger group-hover:flex"
                >
                  <Trash2 size={12} />
                </button>
              </button>
            );
          })}
        </div>
      </aside>

      {/* ── Chat main + optional activity panel ───────────────────────────── */}
      <div className="flex min-w-0 flex-1">
        {/* Chat column */}
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Header */}
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-separator px-5">
            <h2 className="truncate text-sm font-semibold">{currentTitle}</h2>
            {lastAssistant?.agentEvents && lastAssistant.agentEvents.length > 0 && (
              <button
                type="button"
                onClick={() => setActivityOpen((v) => !v)}
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs transition-colors",
                  activityOpen
                    ? "bg-accent-soft text-accent-soft-foreground"
                    : "text-muted hover:bg-surface-secondary hover:text-foreground",
                )}
              >
                <Activity size={13} />
                Activity
                {lastAssistant.thinkingElapsed != null && (
                  <span className="text-muted">· {lastAssistant.thinkingElapsed}s</span>
                )}
              </button>
            )}
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-slim">
            <div className="mx-auto flex max-w-2xl flex-col gap-5 px-6 py-6">
              {messages.length === 0 && !thinking && (
                <div className="mt-20 flex flex-col items-center text-center text-muted">
                  <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent">
                    <Sparkles size={24} />
                  </div>
                  <p className="text-lg font-semibold text-foreground">How can I help?</p>
                  <p className="mt-1 max-w-sm text-sm">
                    Ask anything — I can access your Nextcloud, run commands on your PC, and more.
                  </p>
                </div>
              )}

              {messages.map((m) => <MessageBubble key={m.id} message={m} />)}

              {/* Inline thinking state */}
              {thinking && (
                <div className="flex gap-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground">
                    <Sparkles size={13} />
                  </div>
                  <div className="pt-1.5 text-sm text-muted">
                    <div className="flex items-center gap-1">
                      <Dot /> <Dot delay="150ms" /> <Dot delay="300ms" />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Composer */}
          <div className="border-t border-separator px-5 py-4">
            <form
              onSubmit={submit}
              className="mx-auto flex max-w-2xl flex-col gap-2 rounded-2xl border border-separator bg-surface p-3 shadow-sm transition-colors focus-within:border-accent/60"
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
                placeholder={status === "open" ? "Ask anything…" : "Connecting…"}
                disabled={status !== "open"}
                className="w-full resize-none bg-transparent text-sm outline-none placeholder:text-muted scroll-slim"
              />
              <div className="flex items-center justify-between">
                <ModelSelector
                  provider={provider}
                  model={model}
                  onChange={changeModel}
                />
                <Button
                  type="submit"
                  variant="primary"
                  isIconOnly
                  isDisabled={status !== "open" || !input.trim()}
                  className="h-8 w-8 shrink-0 rounded-full"
                  aria-label="Send"
                >
                  <Send size={14} />
                </Button>
              </div>
            </form>

            {status !== "open" && (
              <p className="mx-auto mt-1.5 max-w-2xl text-center text-xs text-warning">
                Reconnecting to Dax…
              </p>
            )}
          </div>
        </div>

        {/* Activity panel */}
        {activityOpen && lastAssistant?.agentEvents && (
          <ActivityPanel
            events={lastAssistant.agentEvents}
            elapsed={lastAssistant.thinkingElapsed}
            onClose={() => setActivityOpen(false)}
          />
        )}
      </div>

      {/* Tool confirmation modal */}
      {confirmation && (
        <Modal
          open
          title={
            <span className="flex items-center gap-2">
              <ShieldAlert size={18} className="text-warning-soft-foreground" />
              Confirm tool use
            </span>
          }
          footer={
            <>
              <Button variant="ghost" onPress={() => respondConfirmation(confirmation.approval_id, false)}>
                Deny
              </Button>
              <Button variant="primary" onPress={() => respondConfirmation(confirmation.approval_id, true)}>
                Allow
              </Button>
            </>
          }
        >
          <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <Badge color="warning">{confirmation.server_name}</Badge>
              <span className="font-mono text-sm font-medium">{confirmation.tool_name}</span>
            </div>
            {Object.keys(confirmation.arguments).length > 0 && (
              <pre className="overflow-x-auto rounded-xl bg-surface-secondary p-3 font-mono text-xs text-muted scroll-slim">
                {JSON.stringify(confirmation.arguments, null, 2)}
              </pre>
            )}
            <p className="text-xs text-muted">
              Auto-deny in {confirmation.timeout_seconds}s if not answered.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
