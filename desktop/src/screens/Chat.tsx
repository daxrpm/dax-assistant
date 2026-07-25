import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useId,
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
  COMMAND_DECK_SESSION_ID,
  type AgentEvent,
  type ChatMessage,
  type ConfirmationRequest,
} from "../hooks/useChatSocket";
import { cn } from "../lib/cn";
import { useI18n, type Translate } from "../i18n/I18n";
import s from "./Chat.module.css";

/* ---------------- helpers ---------------- */

const SESSION_KEY = "dax.chat.sessionId";

function newSessionId(): string {
  return crypto.randomUUID();
}

function getStoredSessionId(): string {
  const stored = localStorage.getItem(SESSION_KEY);
  return stored && stored !== COMMAND_DECK_SESSION_ID ? stored : newSessionId();
}

function formatRelative(iso: string, t: Translate, locale: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.floor((Date.now() - then) / 60_000);
  if (mins < 1) return t("chat.justNow");
  if (mins < 60) return t("chat.minutesAgo", { count: mins });
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return t("chat.hoursAgo", { count: hrs });
  const days = Math.floor(hrs / 24);
  return days < 7 ? t("chat.daysAgo", { count: days }) : new Date(iso).toLocaleDateString(locale);
}

/* ---------------- agent event rendering ---------------- */

function StepLine({ ev }: { ev: AgentEvent }) {
  const { t } = useI18n();
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
        <span>{ev.error ? t("chat.failed") : t("chat.done")}</span>
      </div>
    );
  }
  return null;
}

/** Post-hoc "Thought for Ns" disclosure on a completed assistant turn. */
function ThoughtToggle({ events, elapsed }: { events: AgentEvent[]; elapsed?: number }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const disclosureId = useId();
  const toolCalls = events.filter((e) => e.type === "tool_call");
  if (toolCalls.length === 0 && elapsed == null) return null;

  return (
    <div>
      <button
        type="button"
        className={s.thoughtToggle}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={disclosureId}
      >
        {open ? <ChevronDownIcon size={12} /> : <ChevronRightIcon size={12} />}
        <span>{elapsed != null ? t("chat.thought", { count: elapsed }) : t("chat.reasoning")}</span>
        {toolCalls.length > 0 && (
          <span>
            · {t("chat.toolsCount", { count: toolCalls.length })}
          </span>
        )}
      </button>
      {open && (
        <div className={s.steps} id={disclosureId}>
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
  const { t } = useI18n();
  const lastCall = [...events].reverse().find((e) => e.type === "tool_call");
  const headline = lastCall
    ? t("chat.using", { tool: `${lastCall.server ? `${lastCall.server} · ` : ""}${lastCall.tool}` })
    : t("chat.thinking");
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
  const { t } = useI18n();
  const items = events.filter(
    (e) => e.type === "tool_call" || e.type === "tool_result",
  );

  return (
    <aside className={s.activity}>
      <div className={s.activityHeader}>
        <div className={s.activityTitle}>
          <ActivityIcon size={14} />
          {t("chat.activity")}
          {live && <Spinner size={11} />}
          {elapsed != null && <span className={s.convMeta}>· {elapsed}s</span>}
        </div>
        <IconButton label={t("chat.closeActivity")} onClick={onClose}>
          <XIcon size={14} />
        </IconButton>
      </div>
      <div className={s.activityBody}>
        {items.length === 0 && <p className={s.activityEmpty}>{t("chat.noToolActivity")}</p>}
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
                <span>{ev.error ? t("chat.error") : t("chat.result")}</span>
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

type ProviderModelField =
  | "anthropic_model"
  | "openai_model"
  | "gemini_model"
  | "deepseek_model"
  | "ollama_model"
  | "codex_model";

export function providerModelField(provider: string): ProviderModelField {
  switch (provider) {
    case "anthropic":
      return "anthropic_model";
    case "openai":
      return "openai_model";
    case "gemini":
      return "gemini_model";
    case "deepseek":
      return "deepseek_model";
    case "codex":
      return "codex_model";
    default:
      return "ollama_model";
  }
}

function ModelSelector({
  provider,
  model,
  onChange,
}: {
  provider: string;
  model: string;
  onChange: (provider: string, model: string) => void;
}) {
  const { t } = useI18n();
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
          <div className={s.modelLoading}>{t("chat.loadingModels")}</div>
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
  const { t } = useI18n();
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
           {t("chat.confirmTool")}
        </>
      }
      footer={
        canSave ? (
          <>
            <Button
              variant="ghost"
              onClick={() => onDecide(request.approval_id, "deny")}
            >
               {t("chat.deny")}
            </Button>
            <Button
              variant="secondary"
              onClick={() => onDecide(request.approval_id, "once")}
            >
               {t("chat.approveOnce")}
            </Button>
            <Button
              variant="primary"
              onClick={() => onDecide(request.approval_id, "save")}
            >
               {t("chat.approveSave")}
            </Button>
          </>
        ) : (
          <>
            <Button
              variant="ghost"
              onClick={() => onDecide(request.approval_id, "deny")}
            >
               {t("chat.deny")}
            </Button>
            <Button
              variant="primary"
              onClick={() =>
                onDecide(
                  request.approval_id,
                  // A shell gate offers "once" (node shells are never savable, so
                  // they arrive without "save"); a plain gate offers "approve".
                  // Send whichever the backend accepts — hardcoding "approve" made
                  // it reject the decision and the confirmation timed out to deny.
                  request.options?.includes("once") ? "once" : "approve",
                )
              }
            >
               {request.options?.includes("once") ? t("chat.approveOnce") : t("chat.allow")}
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
          {t("chat.confirmNote")}
        </p>
      )}

      <div
        className={cn(s.countdown, urgent && s.countdownUrgent)}
        role="timer"
        aria-live={urgent ? "assertive" : "off"}
      >
        <span>{t("chat.autoDeny", { count: remaining })}</span>
        <span
          className={s.countdownTrack}
          role="progressbar"
          aria-label={t("chat.autoDeny", { count: remaining })}
          aria-valuemin={0}
          aria-valuemax={total}
          aria-valuenow={remaining}
        >
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
  const { intlLocale, t } = useI18n();
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
  const conversationListRequest = useRef(0);
  const conversationDetailRequest = useRef(0);

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
        const m = cfg.llm[providerModelField(p)];
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
    const request = ++conversationListRequest.current;
    api
      .conversations(50)
      .then((next) => {
        if (request === conversationListRequest.current) setConversations(next);
      })
      .catch(() => {
        if (request === conversationListRequest.current) setConversations([]);
      });
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
    const request = ++conversationDetailRequest.current;
    try {
      const detail = await api.conversation(conv.id);
      if (request !== conversationDetailRequest.current) return;
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
    conversationDetailRequest.current += 1;
    setInitialMessages([]);
    setActiveConvId(null);
    setSessionId(newSessionId());
  };

  const deleteConv = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    conversationListRequest.current += 1;
    conversationDetailRequest.current += 1;
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
    const key = providerModelField(nextProvider);
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
      ? t("chat.newConversation")
      : t("chat.newChat");

  return (
    <div className={s.chat}>
      <aside className={s.convSidebar} aria-label={t("chat.conversations")}>
        <div className={s.convHeader}>
          <Button variant="primary" size="sm" fullWidth onClick={startNewChat}>
            <PlusIcon size={14} />
            {t("chat.newChat")}
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
             placeholder={t("chat.searchChats")}
             aria-label={t("chat.searchConversations")}
          />
        </div>

        <div className={s.groupHeader}>{t("chat.recent")}</div>

        <div className={s.convList}>
          {filtered.length === 0 && (
            <p className={s.convEmpty}>{search ? t("chat.noMatches") : t("chat.noConversations")}</p>
          )}
          {filtered.map((conv) => (
            <div
              key={conv.id}
              className={cn(
                s.convRow,
                conv.session_key === sessionId && s.convRowSelected,
              )}
            >
              <button
                type="button"
                className={s.convOpen}
                aria-current={conv.session_key === sessionId ? "true" : undefined}
                onClick={() => void openConversation(conv)}
              >
                <span className={s.convIcon}>
                  <ChatIcon size={14} />
                </span>
                <span className={s.convText}>
                  <span className={s.convTitle}>{conv.title || t("chat.newConversation")}</span>
                  <span className={s.convMeta}>{formatRelative(conv.updated_at, t, intlLocale)}</span>
                </span>
              </button>
              <span className={s.convDelete}>
                <IconButton
                  label={t("chat.deleteConversation", { name: conv.title || t("chat.newConversation") })}
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
                title={t("chat.copySession")}
              >
                {idCopied ? <CheckIcon size={13} /> : <LinkIcon size={13} />}
                {idCopied ? t("chat.copied") : t("chat.sessionId")}
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
                  {t("chat.activity")}
                  {thinking && <Spinner size={10} />}
                  {panelElapsed != null && <span>· {panelElapsed}s</span>}
                </button>
              )}
            </div>
          </div>

          <div className={s.scroll} ref={scrollRef} aria-live="polite" aria-busy={thinking}>
            <div className={s.thread}>
              {messages.length === 0 && !thinking && (
                <div className={s.hero}>
                  <div className={s.heroMark}>
                    <SparkleIcon size={22} />
                  </div>
                  <p className={s.heroTitle}>{t("chat.heroTitle")}</p>
                  <p className={s.heroBody}>
                    {t("chat.heroBody")}
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
                placeholder={status === "open" ? t("chat.ask") : t("common.connecting")}
                aria-label={t("chat.message")}
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
                  aria-label={t("deck.send")}
                >
                  <SendIcon size={14} />
                </button>
              </div>
            </form>

            {authFailed ? (
              <p className={cn(s.connectionNote, s.connectionNoteError)}>
                {t("chat.rejected")}
              </p>
            ) : status !== "open" ? (
              <p className={s.connectionNote}>{t("chat.reconnecting")}</p>
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
