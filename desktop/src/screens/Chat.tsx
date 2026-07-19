import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from "react";
import { api } from "../api/client";
import type { ConversationSummary } from "../api/types";
import { Markdown } from "../components/Markdown";
import {
  ActivityIcon,
  AlertIcon,
  ChatIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  LinkIcon,
  PlusIcon,
  SearchIcon,
  SendIcon,
  ShieldIcon,
  SparkleIcon,
  TrashIcon,
  WrenchIcon,
  XIcon,
} from "../components/icons";
import {
  Badge,
  Button,
  IconButton,
  Modal,
  Popover,
  Spinner,
} from "../design/primitives";
import {
  useChatSocket,
  type AgentEvent,
  type ChatMessage,
  type ConfirmationRequest,
} from "../hooks/useChatSocket";
import { cn } from "../lib/cn";
import s from "./Chat.module.css";

/* ---------------- helpers ---------------- */

const SESSION_KEY = "dax.chat.sessionId";

function newSessionId(): string {
  return crypto.randomUUID();
}

function getStoredSessionId(): string {
  return localStorage.getItem(SESSION_KEY) || newSessionId();
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.floor((Date.now() - then) / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return days < 7 ? `${days}d ago` : new Date(iso).toLocaleDateString();
}

/* ---------------- agent event rendering ---------------- */

function StepLine({ ev }: { ev: AgentEvent }) {
  if (ev.type === "tool_call") {
    const label = ev.server ? `${ev.server} · ${ev.tool}` : (ev.tool ?? "");
    return (
      <div className={s.step}>
        <WrenchIcon size={11} />
        <span className={s.stepTool}>{label}</span>
      </div>
    );
  }
  if (ev.type === "tool_result") {
    return (
      <div className={s.step}>
        <span className={ev.error ? s.stepErr : s.stepOk}>
          {ev.error ? <AlertIcon size={11} /> : <CheckIcon size={11} />}
        </span>
        <span className={s.stepTool}>{ev.tool}</span>
        <span>{ev.error ? "failed" : "done"}</span>
      </div>
    );
  }
  return null;
}

/** Post-hoc "Thought for Ns" disclosure on a completed assistant turn. */
function ThoughtToggle({ events, elapsed }: { events: AgentEvent[]; elapsed?: number }) {
  const [open, setOpen] = useState(false);
  const toolCalls = events.filter((e) => e.type === "tool_call");
  if (toolCalls.length === 0 && elapsed == null) return null;

  return (
    <div>
      <button type="button" className={s.thoughtToggle} onClick={() => setOpen((v) => !v)}>
        {open ? <ChevronDownIcon size={12} /> : <ChevronRightIcon size={12} />}
        <span>{elapsed != null ? `Thought for ${elapsed}s` : "Reasoning"}</span>
        {toolCalls.length > 0 && (
          <span>
            · {toolCalls.length} tool{toolCalls.length !== 1 ? "s" : ""}
          </span>
        )}
      </button>
      {open && (
        <div className={s.steps}>
          {events.map((ev, i) => (
            <StepLine key={i} ev={ev} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Live trail while the turn is in flight. */
function ThinkingTrail({ events }: { events: AgentEvent[] }) {
  const lastCall = [...events].reverse().find((e) => e.type === "tool_call");
  const headline = lastCall
    ? `Using ${lastCall.server ? `${lastCall.server} · ` : ""}${lastCall.tool}`
    : "Thinking";
  const steps = events.filter((e) => e.type === "tool_call" || e.type === "tool_result");

  return (
    <div className={s.assistantRow}>
      <div className={s.avatar}>
        <SparkleIcon size={13} />
      </div>
      <div className={s.assistantBody}>
        <span className={s.trailHeadline}>{headline}</span>
        {steps.length > 0 && (
          <div className={s.steps}>
            {steps.map((ev, i) => (
              <StepLine key={i} ev={ev} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className={s.userRow}>
        <div className={s.userBubble}>{message.content}</div>
      </div>
    );
  }
  return (
    <div className={s.assistantRow}>
      <div className={s.avatar}>
        <SparkleIcon size={13} />
      </div>
      <div className={s.assistantBody}>
        {message.agentEvents && message.agentEvents.length > 0 && (
          <ThoughtToggle
            events={message.agentEvents}
            elapsed={message.thinkingElapsed}
          />
        )}
        <Markdown content={message.content} />
      </div>
    </div>
  );
}

/* ---------------- activity panel ---------------- */

function ActivityPanel({
  events,
  elapsed,
  live,
  onClose,
}: {
  events: AgentEvent[];
  elapsed?: number;
  live: boolean;
  onClose: () => void;
}) {
  const items = events.filter(
    (e) => e.type === "tool_call" || e.type === "tool_result",
  );

  return (
    <aside className={s.activity}>
      <div className={s.activityHeader}>
        <div className={s.activityTitle}>
          <ActivityIcon size={14} />
          Activity
          {live && <Spinner size={11} />}
          {elapsed != null && <span className={s.convMeta}>· {elapsed}s</span>}
        </div>
        <IconButton label="Close activity panel" onClick={onClose}>
          <XIcon size={14} />
        </IconButton>
      </div>
      <div className={s.activityBody}>
        {items.length === 0 && <p className={s.activityEmpty}>No tool activity yet</p>}
        {items.map((ev, i) =>
          ev.type === "tool_call" ? (
            <div key={i} className={s.activityItem}>
              <div className={s.activityItemHead}>
                <span className={s.stepIcon}>
                  <WrenchIcon size={11} />
                </span>
                <span className={s.stepTool}>{ev.tool}</span>
              </div>
              {ev.server && <span className={s.activityServer}>{ev.server}</span>}
              {ev.args && Object.keys(ev.args).length > 0 && (
                <pre className={s.activityPre}>{JSON.stringify(ev.args, null, 2)}</pre>
              )}
            </div>
          ) : (
            <div key={i} className={s.activityItem}>
              <div className={s.activityItemHead}>
                <span className={ev.error ? s.stepErr : s.stepOk}>
                  {ev.error ? <AlertIcon size={11} /> : <CheckIcon size={11} />}
                </span>
                <span>{ev.error ? "Error" : "Result"}</span>
              </div>
              {ev.preview && <pre className={s.activityPre}>{ev.preview}</pre>}
            </div>
          ),
        )}
      </div>
    </aside>
  );
}

/* ---------------- model selector ---------------- */

const PROVIDERS = ["openai", "anthropic", "gemini", "deepseek", "ollama", "codex"];

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

  const loadModels = async () => {
    if (Object.keys(models).length > 0) return;
    setLoading(true);
    try {
      setModels(await api.llmModels());
    } catch {
      // A discovery failure leaves the current selection intact.
    } finally {
      setLoading(false);
    }
  };

  const shortModel = model.length > 22 ? `${model.slice(0, 20)}…` : model;

  return (
    <Popover
      open={open}
      onClose={() => setOpen(false)}
      placement="top"
      trigger={
        <button
          type="button"
          className={s.modelTrigger}
          onClick={() => {
            setOpen((v) => !v);
            if (!open) void loadModels();
          }}
        >
          <span className={s.modelProvider}>{provider}</span>
          <span>·</span>
          <span className={s.modelName}>{shortModel}</span>
          <ChevronDownIcon size={11} />
        </button>
      }
    >
      <div className={s.modelMenu}>
        {loading ? (
          <div className={s.modelLoading}>Loading models…</div>
        ) : (
          PROVIDERS.map((prov) => {
            const list = models[prov] ?? [];
            if (list.length === 0) return null;
            return (
              <div key={prov}>
                <div className={s.modelGroup}>{prov}</div>
                {list.map((m) => (
                  <button
                    key={`${prov}:${m}`}
                    type="button"
                    className={cn(
                      s.modelOption,
                      prov === provider && m === model && s.modelOptionSelected,
                    )}
                    onClick={() => {
                      onChange(prov, m);
                      setOpen(false);
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            );
          })
        )}
      </div>
    </Popover>
  );
}

/* ---------------- tool confirmation ---------------- */

/**
 * The countdown is not decoration. `ApprovalManager` denies on timeout
 * (PLAN.md 4.4), so the user must be able to see how long they have left; when
 * it hits zero the modal closes itself because the server has already decided.
 */
function ConfirmationModal({
  request,
  onDecide,
  onExpire,
}: {
  request: ConfirmationRequest;
  onDecide: (approvalId: string, decision: string) => void;
  onExpire: () => void;
}) {
  const total = request.timeout_seconds || 60;
  const [remaining, setRemaining] = useState(total);

  useEffect(() => {
    setRemaining(total);
    const timer = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          onExpire();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [request.approval_id, total, onExpire]);

  const urgent = remaining <= 10;
  const canSave = request.options?.includes("save");

  return (
    <Modal
      open
      title={
        <>
          <ShieldIcon size={16} />
          Confirm tool use
        </>
      }
      footer={
        canSave ? (
          <>
            <Button
              variant="ghost"
              onClick={() => onDecide(request.approval_id, "deny")}
            >
              Deny
            </Button>
            <Button
              variant="secondary"
              onClick={() => onDecide(request.approval_id, "once")}
            >
              Approve once
            </Button>
            <Button
              variant="primary"
              onClick={() => onDecide(request.approval_id, "save")}
            >
              Approve &amp; save
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="ghost"
              onClick={() => onDecide(request.approval_id, "deny")}
            >
              Deny
            </Button>
            <Button
              variant="primary"
              onClick={() => onDecide(request.approval_id, "approve")}
            >
              Allow
            </Button>
          </>
        )
      }
    >
      <div className={s.confirmHead}>
        <Badge tone="warning">{request.server_name}</Badge>
        <span className={s.confirmTool}>{request.tool_name}</span>
      </div>

      {Object.keys(request.arguments ?? {}).length > 0 && (
        <pre className={s.activityPre} style={{ marginLeft: 0 }}>
          {JSON.stringify(request.arguments, null, 2)}
        </pre>
      )}

      {canSave && (
        <p className={s.confirmNote}>
          <strong>Approve &amp; save</strong> adds this command to your allowlist so it
          runs without asking next time. <strong>Approve once</strong> runs it just this
          time. Manage the list under <em>Commands</em>.
        </p>
      )}

      <div className={cn(s.countdown, urgent && s.countdownUrgent)}>
        <span>Auto-deny in {remaining}s</span>
        <span className={s.countdownTrack}>
          <span
            className={cn(s.countdownFill, urgent && s.countdownFillUrgent)}
            style={{ width: `${(remaining / total) * 100}%` }}
          />
        </span>
      </div>
    </Modal>
  );
}

/* ---------------- screen ---------------- */

export function Chat() {
  const [sessionId, setSessionId] = useState<string>(getStoredSessionId);
  const [initialMessages, setInitialMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const [idCopied, setIdCopied] = useState(false);
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState("gpt-4o");
  const [input, setInput] = useState("");

  const {
    messages,
    status,
    authFailed,
    thinking,
    liveEvents,
    confirmation,
    send,
    respondConfirmation,
    expireConfirmation,
  } = useChatSocket(sessionId, initialMessages);

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const panelEvents: AgentEvent[] =
    thinking && liveEvents.length > 0 ? liveEvents : (lastAssistant?.agentEvents ?? []);
  const panelElapsed = thinking ? undefined : lastAssistant?.thinkingElapsed;

  useEffect(() => {
    localStorage.setItem(SESSION_KEY, sessionId);
  }, [sessionId]);

  // Load the configured provider/model so the selector opens on the truth.
  useEffect(() => {
    api
      .config()
      .then((cfg) => {
        const p = cfg.llm.default_provider;
        setProvider(p);
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
      .catch(() => {
        // Selector keeps its defaults; chat still works.
      });
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, thinking]);

  // Autogrow the composer.
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [input]);

  const loadConversations = useCallback(() => {
    api
      .conversations(50)
      .then(setConversations)
      .catch(() => setConversations([]));
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // The backend titles a conversation after persisting the turn, so refresh a
  // beat later rather than immediately.
  const lastCount = useRef(messages.length);
  useEffect(() => {
    if (messages.length > lastCount.current) {
      lastCount.current = messages.length;
      const t = setTimeout(loadConversations, 1500);
      return () => clearTimeout(t);
    }
  }, [messages.length, loadConversations]);

  const openConversation = async (conv: ConversationSummary) => {
    if (conv.id === activeConvId) return;
    try {
      const detail = await api.conversation(conv.id);
      setInitialMessages(
        detail.messages.map((m) => ({
          id: m.id,
          role: m.role === "user" ? "user" : "assistant",
          content: m.content,
          timestamp: m.timestamp,
        })),
      );
      setSessionId(conv.session_key);
      setActiveConvId(conv.id);
    } catch {
      // Leave the current conversation in place on a load failure.
    }
  };

  const startNewChat = () => {
    setInitialMessages([]);
    setActiveConvId(null);
    setSessionId(newSessionId());
  };

  const deleteConv = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    setDeletingId(convId);
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (conversations.find((c) => c.id === convId)?.session_key === sessionId) {
        startNewChat();
      }
    } catch {
      // Keep the row; the next refresh reconciles.
    } finally {
      setDeletingId(null);
    }
  };

  const copySessionId = async () => {
    try {
      await navigator.clipboard.writeText(sessionId);
      setIdCopied(true);
      setTimeout(() => setIdCopied(false), 1500);
    } catch {
      // Clipboard permission denied — nothing useful to say.
    }
  };

  const changeModel = async (nextProvider: string, nextModel: string) => {
    setProvider(nextProvider);
    setModel(nextModel);
    const key =
      nextProvider === "anthropic"
        ? "anthropic_model"
        : nextProvider === "openai"
          ? "openai_model"
          : nextProvider === "gemini"
            ? "gemini_model"
            : nextProvider === "deepseek"
              ? "deepseek_model"
              : "ollama_model";
    try {
      await api.updateLLM({ default_provider: nextProvider, [key]: nextModel });
    } catch {
      // The router keeps its previous providers; surfacing this would need a
      // toast the composer has no room for.
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || status !== "open") return;
    send(text);
    setInput("");
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter(
      (c) =>
        c.title.toLowerCase().includes(q) || (c.preview ?? "").toLowerCase().includes(q),
    );
  }, [conversations, search]);

  const title = activeConvId
    ? (conversations.find((c) => c.id === activeConvId)?.title ?? "Chat")
    : messages.length > 0
      ? "New conversation"
      : "New chat";

  return (
    <div className={s.chat}>
      <aside className={s.convSidebar}>
        <div className={s.convHeader}>
          <Button variant="primary" size="sm" fullWidth onClick={startNewChat}>
            <PlusIcon size={14} />
            New chat
          </Button>
        </div>

        <div className={s.searchWrap}>
          <span className={s.searchIcon}>
            <SearchIcon size={13} />
          </span>
          <input
            className={s.searchInput}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search chats"
          />
        </div>

        <div className={s.groupHeader}>Recent</div>

        <div className={s.convList}>
          {filtered.length === 0 && (
            <p className={s.convEmpty}>{search ? "No matches" : "No conversations yet"}</p>
          )}
          {filtered.map((conv) => (
            <div
              key={conv.id}
              role="button"
              tabIndex={0}
              onClick={() => void openConversation(conv)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") void openConversation(conv);
              }}
              className={cn(
                s.convRow,
                conv.session_key === sessionId && s.convRowSelected,
              )}
            >
              <span className={s.convIcon}>
                <ChatIcon size={14} />
              </span>
              <div className={s.convText}>
                <div className={s.convTitle}>{conv.title || "New conversation"}</div>
                <div className={s.convMeta}>{formatRelative(conv.updated_at)}</div>
              </div>
              <span className={s.convDelete}>
                <IconButton
                  label="Delete conversation"
                  danger
                  disabled={deletingId === conv.id}
                  onClick={(e) => void deleteConv(e, conv.id)}
                >
                  <TrashIcon size={12} />
                </IconButton>
              </span>
            </div>
          ))}
        </div>
      </aside>

      <div className={s.main}>
        <div className={s.column}>
          <div className={s.header}>
            <h2 className={s.headerTitle}>{title}</h2>
            <div className={s.headerActions}>
              <button
                type="button"
                className={s.headerButton}
                onClick={() => void copySessionId()}
                title="Copy this conversation's session id"
              >
                {idCopied ? <CheckIcon size={13} /> : <LinkIcon size={13} />}
                {idCopied ? "Copied" : "Session id"}
              </button>
              {panelEvents.length > 0 && (
                <button
                  type="button"
                  className={cn(
                    s.headerButton,
                    activityOpen && s.headerButtonActive,
                  )}
                  onClick={() => setActivityOpen((v) => !v)}
                >
                  <ActivityIcon size={13} />
                  Activity
                  {thinking && <Spinner size={10} />}
                  {panelElapsed != null && <span>· {panelElapsed}s</span>}
                </button>
              )}
            </div>
          </div>

          <div className={s.scroll} ref={scrollRef}>
            <div className={s.thread}>
              {messages.length === 0 && !thinking && (
                <div className={s.hero}>
                  <div className={s.heroMark}>
                    <SparkleIcon size={22} />
                  </div>
                  <p className={s.heroTitle}>How can I help?</p>
                  <p className={s.heroBody}>
                    Ask anything — I can reach your files, run allowlisted commands, and
                    use every connected MCP server.
                  </p>
                </div>
              )}

              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}

              {thinking && <ThinkingTrail events={liveEvents} />}
            </div>
          </div>

          <div className={s.composerWrap}>
            <form className={s.composer} onSubmit={submit}>
              <textarea
                ref={textareaRef}
                className={cn(s.composerInput, "selectable")}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit(e);
                  }
                }}
                rows={1}
                disabled={status !== "open"}
                placeholder={status === "open" ? "Ask anything…" : "Connecting…"}
              />
              <div className={s.composerBar}>
                <ModelSelector
                  provider={provider}
                  model={model}
                  onChange={(p, m) => void changeModel(p, m)}
                />
                {/*
                  Voice HUD entry point belongs here (PLAN.md 6.2). Deferred to
                  M4 — it depends on `/ws/voice`, which is being built now.
                */}
                <button
                  type="submit"
                  className={s.sendButton}
                  disabled={status !== "open" || !input.trim()}
                  aria-label="Send"
                >
                  <SendIcon size={14} />
                </button>
              </div>
            </form>

            {authFailed ? (
              <p className={cn(s.connectionNote, s.connectionNoteError)}>
                Chat rejected this session. Sign out and back in.
              </p>
            ) : status !== "open" ? (
              <p className={s.connectionNote}>Reconnecting to Dax…</p>
            ) : null}
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

      {confirmation && (
        <ConfirmationModal
          request={confirmation}
          onDecide={respondConfirmation}
          onExpire={expireConfirmation}
        />
      )}
    </div>
  );
}
