import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Button, Spinner } from "@heroui/react";
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
  Link2,
  Check,
  Search,
} from "lucide-react";
import { useChatSocket, type ChatMessage, type AgentEvent } from "../hooks/useChatSocket";
import { api, type ConversationSummary } from "../api/client";
import { Markdown } from "../components/Markdown";
import { Modal, Badge } from "../components/ui";
import { ThemeToggle } from "../components/ThemeToggle";
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

/* ── Assistant avatar ─────────────────────────────────────────────────────── */

function AssistantAvatar() {
  return (
    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent/70 text-accent-foreground shadow-sm">
      <Sparkles size={13} />
    </div>
  );
}

/* ── Single tool step line (used in thinking trail + collapsed thought) ─────── */

function StepLine({ ev }: { ev: AgentEvent }) {
  if (ev.type === "tool_call") {
    const label = ev.server ? `${ev.server} · ${ev.tool}` : ev.tool ?? "";
    return (
      <div className="flex items-center gap-2 text-xs text-muted">
        <Wrench size={11} className="shrink-0 text-accent" />
        <span className="truncate">
          Using <span className="font-mono text-foreground/80">{label}</span>
        </span>
      </div>
    );
  }
  if (ev.type === "tool_result") {
    return (
      <div className="flex items-center gap-2 text-xs text-muted">
        {ev.error ? (
          <AlertCircle size={11} className="shrink-0 text-danger-soft-foreground" />
        ) : (
          <CheckCircle2 size={11} className="shrink-0 text-success-soft-foreground" />
        )}
        <span className="truncate font-mono text-foreground/60">{ev.tool}</span>
        <span>{ev.error ? "failed" : "done"}</span>
      </div>
    );
  }
  return null;
}

/* ── Collapsed "Thought for Ns" (after the turn completes) ─────────────────── */

function ThoughtToggle({ events, elapsed }: { events: AgentEvent[]; elapsed?: number }) {
  const [open, setOpen] = useState(false);
  const toolCalls = events.filter((e) => e.type === "tool_call");
  if (toolCalls.length === 0 && elapsed == null) return null;

  const label = elapsed != null ? `Thought for ${elapsed}s` : "Reasoning";

  return (
    <div className="mb-1.5">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-muted/80 transition-colors hover:text-foreground"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span>{label}</span>
        {toolCalls.length > 0 && (
          <span className="text-muted/60">· {toolCalls.length} tool{toolCalls.length !== 1 ? "s" : ""}</span>
        )}
      </button>
      {open && (
        <div className="mt-2 flex flex-col gap-1.5 border-l border-separator pl-3">
          {events.map((ev, i) => (
            <StepLine key={i} ev={ev} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Live thinking trail (in-flight, ChatGPT-style) ───────────────────────── */

function ThinkingTrail({ events }: { events: AgentEvent[] }) {
  const lastCall = [...events].reverse().find((e) => e.type === "tool_call");
  const headline = lastCall
    ? `Using ${lastCall.server ? `${lastCall.server} · ` : ""}${lastCall.tool}`
    : "Thinking";
  const steps = events.filter((e) => e.type === "tool_call" || e.type === "tool_result");

  return (
    <div className="flex gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1 pt-0.5">
        <span className="bg-gradient-to-r from-muted via-foreground to-muted bg-[length:200%_100%] bg-clip-text text-sm font-medium text-transparent animate-[shimmer_2.5s_linear_infinite]">
          {headline}
        </span>
        {steps.length > 0 && (
          <div className="mt-2 flex flex-col gap-1.5 border-l border-separator pl-3">
            {steps.map((ev, i) => (
              <StepLine key={i} ev={ev} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Message bubble ───────────────────────────────────────────────────────── */

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-3xl rounded-br-lg bg-surface-secondary px-4 py-2.5 text-sm leading-relaxed">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1 pt-0.5">
        {message.agentEvents && message.agentEvents.length > 0 && (
          <ThoughtToggle events={message.agentEvents} elapsed={message.thinkingElapsed} />
        )}
        <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
          <Markdown content={message.content} />
        </div>
      </div>
    </div>
  );
}

/* ── Activity panel ───────────────────────────────────────────────────────── */

function ActivityPanel({
  events,
  elapsed,
  live = false,
  onClose,
}: {
  events: AgentEvent[];
  elapsed?: number;
  live?: boolean;
  onClose: () => void;
}) {
  const toolCalls = events.filter((e) => e.type === "tool_call" || e.type === "tool_result");

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-l border-separator bg-surface">
      <div className="flex h-12 items-center justify-between border-b border-separator px-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Activity size={15} />
          Activity
          {live && <Spinner size="sm" />}
          {elapsed != null && <span className="text-xs font-normal text-muted">· {elapsed}s</span>}
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
                    {ev.server && <span className="ml-4 text-[10px] text-muted">{ev.server}</span>}
                    {ev.args && Object.keys(ev.args).length > 0 && (
                      <pre className="ml-4 overflow-x-auto rounded-lg bg-surface-secondary p-1.5 font-mono text-[10px] text-muted scroll-slim">
                        {JSON.stringify(ev.args, null, 2)}
                      </pre>
                    )}
                  </div>
                );
              }
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
            })}
          </div>
        )}
      </div>
    </aside>
  );
}

/* ── Model selector ───────────────────────────────────────────────────────── */

const PROVIDERS = ["openai", "anthropic", "gemini", "deepseek", "ollama", "codex"] as const;

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
      setModels(await api.listLLMModels());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  };

  const shortModel = model.length > 22 ? model.slice(0, 20) + "…" : model;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((v) => !v);
          if (!open) loadModels();
        }}
        className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs text-muted transition-colors hover:bg-surface-secondary hover:text-foreground"
      >
        <span className="capitalize">{provider}</span>
        <span className="text-muted/40">·</span>
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
                        onClick={() => {
                          onChange(prov, m);
                          setOpen(false);
                        }}
                        className={cn(
                          "flex w-full items-center px-3 py-1.5 text-left text-xs transition-colors hover:bg-surface-secondary",
                          prov === provider && m === model
                            ? "font-medium text-accent"
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
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();
  const [sessionId, setSessionId] = useState<string>(getStoredSessionId);
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o");

  const { messages, status, thinking, liveEvents, confirmation, send, respondConfirmation } =
    useChatSocket(sessionId, initialMessages);

  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const panelEvents: AgentEvent[] =
    thinking && liveEvents.length > 0 ? liveEvents : lastAssistant?.agentEvents ?? [];
  const panelElapsed = thinking ? undefined : lastAssistant?.thinkingElapsed;

  // Each chat has a unique URL (/c/:sessionId). If we land on "/" without one,
  // redirect to a stable link so the conversation is always shareable — just
  // like ChatGPT.
  useEffect(() => {
    if (!urlSessionId) navigate(`/c/${sessionId}`, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlSessionId]);

  // Load current provider/model from config
  useEffect(() => {
    api
      .getConfig()
      .then((cfg) => {
        setProvider(cfg.llm.default_provider);
        const p = cfg.llm.default_provider;
        const m =
          p === "anthropic"
            ? cfg.llm.anthropic_model
            : p === "openai"
              ? cfg.llm.openai_model
              : p === "gemini"
                ? cfg.llm.gemini_model
                : p === "deepseek"
                  ? cfg.llm.deepseek_model
                  : cfg.llm.ollama_model;
        if (m) setModel(m);
      })
      .catch(() => {});
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
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [input]);

  const loadConversations = useCallback(() => {
    api.listConversations(50).then(setConversations).catch(() => setConversations([]));
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const lastMessageCount = useRef(messages.length);
  useEffect(() => {
    if (messages.length > lastMessageCount.current) {
      lastMessageCount.current = messages.length;
      const t = setTimeout(loadConversations, 1500);
      return () => clearTimeout(t);
    }
  }, [messages.length, loadConversations]);

  // Drive the active conversation entirely from the URL so deep links and
  // back/forward navigation always reflect the right chat.
  const loadSession = useCallback(
    async (sk: string) => {
      const conv = conversations.find((c) => c.session_key === sk);
      if (!conv) {
        setSessionId(sk);
        setInitialMessages([]);
        setActiveConvId(null);
        return;
      }
      if (conv.id === activeConvId && sk === sessionId) return;
      try {
        const detail = await api.getConversation(conv.id);
        setInitialMessages(
          detail.messages.map((m) => ({
            id: m.id,
            role: m.role as "user" | "assistant",
            content: m.content,
            timestamp: m.timestamp,
          })),
        );
        setSessionId(conv.session_key);
        setActiveConvId(conv.id);
      } catch {
        /* ignore */
      }
    },
    [conversations, activeConvId, sessionId],
  );

  useEffect(() => {
    if (urlSessionId) loadSession(urlSessionId);
  }, [urlSessionId, loadSession]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || status !== "open") return;
    send(text);
    setInput("");
  };

  const startNewChat = () => navigate(`/c/${newSessionId()}`);
  const openConversation = (conv: ConversationSummary) => navigate(`/c/${conv.session_key}`);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/c/${sessionId}`);
      setLinkCopied(true);
      setTimeout(() => setLinkCopied(false), 1500);
    } catch {
      /* ignore */
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
        newProvider === "anthropic"
          ? "anthropic_model"
          : newProvider === "openai"
            ? "openai_model"
            : newProvider === "gemini"
              ? "gemini_model"
              : newProvider === "deepseek"
                ? "deepseek_model"
                : "ollama_model";
      await api.updateLLM({ default_provider: newProvider, [modelKey]: newModel });
    } catch {
      /* ignore */
    }
  };

  const filteredConversations = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter(
      (c) => c.title.toLowerCase().includes(q) || c.preview?.toLowerCase().includes(q),
    );
  }, [conversations, search]);

  const currentTitle = activeConvId
    ? conversations.find((c) => c.id === activeConvId)?.title ?? "Chat"
    : messages.length > 0
      ? "New conversation"
      : "New chat";

  return (
    <div className="flex h-full">
      {/* ── Conversation sidebar ───────────────────────────────────────────── */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-separator bg-surface">
        <div className="p-3">
          <Button variant="primary" size="sm" className="w-full justify-center gap-2" onPress={startNewChat}>
            <Plus size={15} />
            New chat
          </Button>
        </div>

        <div className="px-3 pb-2">
          <div className="relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search chats"
              className="w-full rounded-lg border border-separator bg-background py-1.5 pl-8 pr-2 text-xs outline-none transition-colors placeholder:text-muted focus:border-accent/60"
            />
          </div>
        </div>

        <p className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted">
          Recent
        </p>
        <div className="flex-1 overflow-y-auto scroll-slim px-2 pb-3">
          {filteredConversations.length === 0 && (
            <p className="px-3 py-4 text-center text-xs text-muted">
              {search ? "No matches" : "No conversations yet"}
            </p>
          )}
          {filteredConversations.map((conv) => {
            const isActive = conv.session_key === sessionId;
            return (
              <button
                key={conv.id}
                onClick={() => openConversation(conv)}
                className={cn(
                  "group relative flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left transition-colors",
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
                  <p className="truncate text-xs font-medium">{conv.title || "New conversation"}</p>
                  <p className="text-[10px] text-muted">{formatRelative(conv.updated_at)}</p>
                </div>
                <span
                  role="button"
                  tabIndex={-1}
                  onClick={(e) => deleteConv(e, conv.id)}
                  className="hidden rounded-md p-0.5 text-muted hover:text-danger group-hover:flex"
                  aria-disabled={deletingId === conv.id}
                >
                  <Trash2 size={12} />
                </span>
              </button>
            );
          })}
        </div>
      </aside>

      {/* ── Chat main + optional activity panel ───────────────────────────── */}
      <div className="flex min-w-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          {/* Header */}
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-separator px-5">
            <h2 className="truncate text-sm font-semibold">{currentTitle}</h2>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={copyLink}
                title="Copy link to this chat"
                className="flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs text-muted transition-colors hover:bg-surface-secondary hover:text-foreground"
              >
                {linkCopied ? <Check size={13} /> : <Link2 size={13} />}
                {linkCopied ? "Copied" : "Share"}
              </button>
              {panelEvents.length > 0 && (
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
                  {thinking && <Loader2 size={11} className="animate-spin" />}
                  {panelElapsed != null && <span className="text-muted">· {panelElapsed}s</span>}
                </button>
              )}
              <ThemeToggle />
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto scroll-slim">
            <div className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-8">
              {messages.length === 0 && !thinking && (
                <div className="mt-24 flex flex-col items-center text-center text-muted">
                  <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-accent to-accent/70 text-accent-foreground shadow">
                    <Sparkles size={24} />
                  </div>
                  <p className="text-xl font-semibold text-foreground">How can I help?</p>
                  <p className="mt-1.5 max-w-sm text-sm">
                    Ask anything — I can access your Nextcloud, run commands on your PC, and more.
                  </p>
                </div>
              )}

              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}

              {thinking && <ThinkingTrail events={liveEvents} />}
            </div>
          </div>

          {/* Composer */}
          <div className="px-5 pb-5">
            <form
              onSubmit={submit}
              className="mx-auto flex max-w-3xl flex-col gap-2 rounded-3xl border border-separator bg-surface p-3 shadow-sm transition-colors focus-within:border-accent/60"
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
                className="w-full resize-none bg-transparent px-2 pt-1 text-sm outline-none placeholder:text-muted scroll-slim"
              />
              <div className="flex items-center justify-between">
                <ModelSelector provider={provider} model={model} onChange={changeModel} />
                <Button
                  type="submit"
                  variant="primary"
                  isIconOnly
                  isDisabled={status !== "open" || !input.trim()}
                  className="h-9 w-9 shrink-0 rounded-full"
                  aria-label="Send"
                >
                  <Send size={15} />
                </Button>
              </div>
            </form>
            {status !== "open" && (
              <p className="mx-auto mt-1.5 max-w-3xl text-center text-xs text-warning">
                Reconnecting to Dax…
              </p>
            )}
          </div>
        </div>

        {activityOpen && panelEvents.length > 0 && (
          <ActivityPanel
            events={panelEvents}
            elapsed={panelElapsed}
            live={thinking}
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
            confirmation.options?.includes("save") ? (
              <>
                <Button variant="ghost" onPress={() => respondConfirmation(confirmation.approval_id, "deny")}>
                  Deny
                </Button>
                <Button variant="ghost" onPress={() => respondConfirmation(confirmation.approval_id, "once")}>
                  Approve once
                </Button>
                <Button variant="primary" onPress={() => respondConfirmation(confirmation.approval_id, "save")}>
                  Approve &amp; save
                </Button>
              </>
            ) : (
              <>
                <Button variant="ghost" onPress={() => respondConfirmation(confirmation.approval_id, "deny")}>
                  Deny
                </Button>
                <Button variant="primary" onPress={() => respondConfirmation(confirmation.approval_id, "approve")}>
                  Allow
                </Button>
              </>
            )
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
            {confirmation.options?.includes("save") && (
              <p className="text-xs text-muted">
                <strong>Approve &amp; save</strong> adds this command to your allowlist
                so it runs without asking next time. <strong>Approve once</strong> runs
                it just this time. Manage the list under <em>Commands</em>.
              </p>
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
