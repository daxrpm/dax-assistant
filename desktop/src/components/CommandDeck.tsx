import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { MCPServerStatus, StatusResponse, ToolAuditEntry } from "../api/types";
import { AppIcon } from "./AppIcon";
import {
  COMMAND_DECK_SESSION_ID,
  useChatSocket,
  type AgentEvent,
} from "../hooks/useChatSocket";
import { useLogStream } from "../hooks/useLogStream";
import { useVoiceSocket, type LevelFrame, type PipelineState } from "../hooks/useVoiceSocket";
import { cn } from "../lib/cn";
import {
  isLoopbackBackend,
  readClientMetrics,
  readServerMetrics,
  type HostMetrics,
} from "../lib/hostMetrics";
import { formatCountdown } from "../lib/voiceSession";
import { useI18n } from "../i18n/I18n";
import { useConfig } from "../hooks/useConfig";
import { SendIcon } from "./icons";
import { VoiceOrb, type OrbState, type VoiceOrbHandle } from "./VoiceOrb";
import { NowPlaying } from "./NowPlaying";
import { PairedDevices } from "./PairedDevices";
import s from "./CommandDeck.module.css";

/**
 * The command deck (PLAN.md 5.0, "Structure: the command deck, not a sidebar").
 *
 * The orb is the subject, flanked by two columns that are **glanceable, not
 * navigable**: nothing in them requires a click to learn, and none of them is
 * a link. Navigation lives in ⌘K instead. The log tail is always present and
 * deliberately quiet — an assistant that touches your files must be auditable
 * without going looking for it.
 */

const PIPELINE_KEY = {
  idle: "deck.idle", listening: "deck.listening", processing: "deck.processing",
  speaking: "deck.speaking", conversing: "deck.conversing",
} as const;

/** `conversing` is a pipeline state the orb does not model; it reads as busy. */
function toOrbState(state: PipelineState): OrbState {
  return state === "conversing" ? "listening" : state;
}

/* ---------------- live orb ---------------- */

/**
 * Isolates the ~12.5 Hz level stream into a leaf that renders nothing but the
 * orb, and coalesces frames onto a single rAF so a burst cannot schedule more
 * work than the display can show (PLAN 5.0, "The voice orb").
 */
function LiveOrb({
  state,
  registerLevelSink,
}: {
  state: PipelineState;
  registerLevelSink: (sink: ((frame: LevelFrame) => void) | null) => void;
}) {
  const { t } = useI18n();
  const orbRef = useRef<VoiceOrbHandle>(null);

  useEffect(() => {
    registerLevelSink((frame) => orbRef.current?.setLevel(frame));
    return () => registerLevelSink(null);
  }, [registerLevelSink]);

  return (
    <VoiceOrb
      ref={orbRef}
      state={toOrbState(state)}
      size={220}
      ariaLabel={t(PIPELINE_KEY[state])}
    />
  );
}

/* ---------------- tool activity ---------------- */

interface ToolRun {
  id: number;
  tool: string;
  server: string;
  startedAt: number;
  /** Client-observed round trip, ms. Null while still running. */
  elapsedMs: number | null;
  error: boolean;
}

let runSeq = 0;

/**
 * Latencies for the current turn.
 *
 * The backend does not time individual tools — `ToolAuditEntry` carries a
 * timestamp and a status but no duration, and only the turn total arrives, on
 * the `done` event. So the deck times the `tool_call` → `tool_result` gap
 * itself. That is a genuine measurement of the round trip as the client sees
 * it, which is why the panel labels it "observada".
 */
function useToolRuns(liveEvents: AgentEvent[]): ToolRun[] {
  const [runs, setRuns] = useState<ToolRun[]>([]);
  const consumed = useRef(0);

  useEffect(() => {
    // A new turn clears the live list; `useChatSocket` resets `liveEvents` to
    // an empty array when the assistant's answer lands.
    if (liveEvents.length === 0) {
      consumed.current = 0;
      return;
    }
    if (liveEvents.length <= consumed.current) return;

    const fresh = liveEvents.slice(consumed.current);
    consumed.current = liveEvents.length;

    setRuns((prev) => {
      let next = prev;
      for (const event of fresh) {
        if (event.type === "tool_call") {
          next = [
            {
              id: ++runSeq,
              tool: event.tool ?? "?",
              server: event.server ?? "",
              startedAt: Date.now(),
              elapsedMs: null,
              error: false,
            },
            ...next,
          ].slice(0, 12);
        } else if (event.type === "tool_result") {
          // Match the most recent still-running call for this tool: the agent
          // can invoke the same tool more than once in a turn.
          const index = next.findIndex(
            (run) => run.tool === (event.tool ?? "?") && run.elapsedMs === null,
          );
          if (index === -1) continue;
          next = next.map((run, i) =>
            i === index
              ? {
                  ...run,
                  elapsedMs: Date.now() - run.startedAt,
                  error: Boolean(event.error),
                }
              : run,
          );
        }
      }
      return next;
    });
  }, [liveEvents]);

  return runs;
}

/* ---------------- panes ---------------- */

function Pane({
  title,
  meta,
  className,
  children,
}: {
  title: string;
  meta?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={cn(s.pane, className)}>
      <header className={s.paneHead}>
        <span className={s.paneTitle}>{title}</span>
        {meta && <span className={s.paneMeta}>{meta}</span>}
      </header>
      {children}
    </section>
  );
}

function Row({
  label,
  value,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  tone?: "muted" | "warning" | "danger" | "success";
}) {
  return (
    <div className={s.row}>
      <span className={s.rowLabel}>{label}</span>
      <span className={cn(s.rowValue, tone && s[tone])}>{value}</span>
    </div>
  );
}

/** A meter that renders its own absence rather than a plausible-looking bar. */
function Meter({ label, fraction }: { label: string; fraction: number | null }) {
  const { t } = useI18n();
  if (fraction === null) {
    return <Row label={label} value={t("common.unavailable")} tone="muted" />;
  }
  return (
    <div className={s.meterRow}>
      <div className={s.row}>
        <span className={s.rowLabel}>{label}</span>
        <span className={s.rowValue}>{Math.round(fraction * 100)}%</span>
      </div>
      <div className={s.meterTrack}>
        <div className={s.meterFill} style={{ width: `${fraction * 100}%` }} />
      </div>
    </div>
  );
}

function MetricsPane({ title, metrics }: { title: string; metrics: HostMetrics | null }) {
  const { t } = useI18n();
  return (
    <Pane title={title} meta={metrics ? null : t("deck.noData")}>
      <Meter label="CPU" fraction={metrics?.cpu ?? null} />
      <Meter label={t("deck.memory")} fraction={metrics?.memory ?? null} />
      <Meter label={t("deck.disk")} fraction={metrics?.disk ?? null} />
      <Row
        label={t("deck.uptime")}
        value={metrics ? `${Math.floor(metrics.uptimeSeconds / 3600)} h` : t("common.unavailable")}
        tone={metrics ? undefined : "muted"}
      />
    </Pane>
  );
}

/* ---------------- deck ---------------- */

export function CommandDeck({ onOpenPalette }: { onOpenPalette: () => void }) {
  const { intlLocale, t } = useI18n();
  // The level sink is handed to the orb leaf so frames never enter the deck's
  // own state — see LiveOrb.
  const levelSink = useRef<((frame: LevelFrame) => void) | null>(null);
  const registerLevelSink = useCallback((sink: ((frame: LevelFrame) => void) | null) => {
    levelSink.current = sink;
  }, []);
  const onLevel = useCallback((frame: LevelFrame) => {
    levelSink.current?.(frame);
  }, []);

  const voice = useVoiceSocket({ onLevel });
  const { config } = useConfig();
  const chat = useChatSocket(COMMAND_DECK_SESSION_ID);
  const runs = useToolRuns(chat.liveEvents);
  const { logs, seed } = useLogStream();

  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [servers, setServers] = useState<MCPServerStatus[]>([]);
  const [audit, setAudit] = useState<ToolAuditEntry[]>([]);
  const [clientMetrics, setClientMetrics] = useState<HostMetrics | null>(null);
  const [serverMetrics, setServerMetrics] = useState<HostMetrics | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [draft, setDraft] = useState("");
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null);

  /* clock — one tick a second drives both the local time and the countdown */
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const refresh = useCallback(async () => {
    const [nextStatus, nextServers, nextAudit, nextClientMetrics, nextServerMetrics] = await Promise.all([
      api.status().catch(() => null),
      api.mcpStatus().catch(() => [] as MCPServerStatus[]),
      api.toolAudit(12).catch(() => [] as ToolAuditEntry[]),
      readClientMetrics().catch(() => null),
      readServerMetrics().catch(() => null),
    ]);
    if (nextStatus) setStatus(nextStatus);
    setServers(nextServers);
    setAudit(nextAudit);
    setClientMetrics(nextClientMetrics);
    setServerMetrics(nextServerMetrics);
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  /* Seed the log tail so the pane is not blank until something happens. */
  useEffect(() => {
    void api
      .logs(60)
      .then(seed)
      .catch(() => undefined);
  }, [seed]);

  const remainingSessionSeconds = voice.sessionExpiresAt
    ? Math.max(0, voice.sessionExpiresAt - now / 1000)
    : null;
  const loopback = isLoopbackBackend();
  const collapsedMetrics = clientMetrics ?? serverMetrics;
  const connectedServers = servers.filter((server) => server.connected).length;
  const tail = logs.slice(-14);
  const lastAssistant = [...chat.messages].reverse().find((m) => m.role === "assistant");

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    chat.send(text);
    setDraft("");
  }

  return (
    <div className={s.deck}>
      {/* ---------------- top bar ---------------- */}
      <header className={s.topBar}>
        <div className={s.brandGroup}>
          <AppIcon size={26} className={s.brandIcon} />
          <span className={s.brand}>Dax</span>
          <button type="button" className={s.paletteHint} onClick={onOpenPalette}>
            <kbd className={s.kbd}>⌘K</kbd>
            <span>{t("shell.commands")}</span>
          </button>
        </div>

        <div className={s.statusSet}>
          <span className={s.statusItem}>
            <span
              className={cn(
                s.led,
                voice.state === "idle" ? s.ledIdle : s.ledLive,
                !voice.connected && s.ledOff,
              )}
            />
            <span className={s.statusValue}>{t(PIPELINE_KEY[voice.state])}</span>
          </span>

          <span className={s.statusItem}>
            <span className={s.statusLabel}>{t("deck.session")}</span>
            <span className={s.statusMono}>
              {voice.conversationId ? voice.conversationId.slice(0, 8) : "—"}
            </span>
          </span>

          <span className={s.statusItem}>
            <span className={s.statusLabel}>{t("deck.expires")}</span>
            <span
              className={cn(
                s.statusMono,
                remainingSessionSeconds !== null &&
                  remainingSessionSeconds < 60 &&
                  s.warning,
              )}
              title={t("deck.expiryTitle")}
            >
              {formatCountdown(remainingSessionSeconds)}
            </span>
          </span>

          <span className={s.statusItem}>
            <span className={s.statusMono}>
              {new Date(now).toLocaleTimeString(intlLocale, {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          </span>
        </div>
      </header>

      {/* ---------------- left: your machine ---------------- */}
      <div className={s.column}>
        {loopback ? (
          <MetricsPane title={t("deck.machine")} metrics={collapsedMetrics} />
        ) : (
          <>
            <MetricsPane title={t("deck.client")} metrics={clientMetrics} />
            <MetricsPane title={t("deck.server")} metrics={serverMetrics} />
          </>
        )}

        <Pane title={t("deck.devices")}>
          <PairedDevices />
        </Pane>

        <Pane title={t("deck.voice")} meta={voice.connected ? t("deck.live") : t("common.disconnected")}>
          <Row
            label={t("deck.turns")}
            value={voice.conversationId ? voice.turns : "—"}
            tone={voice.conversationId ? undefined : "muted"}
          />
          <Row
            label={t("deck.followup")}
            value={
              config ? `${config.voice.followup_activation_ms} ms` : "—"
            }
            tone={config ? undefined : "muted"}
          />
          <Row
            label={t("deck.speakerVerified")}
            value={
              !config?.voice.speaker_verification
                ? t("common.disabled")
                : voice.speaker === null
                  ? t("deck.unverified")
                  : voice.speaker.verified
                    ? t("common.yes")
                    : t("common.no")
            }
            tone={
              !config?.voice.speaker_verification
                ? "muted"
                : voice.speaker?.verified === false
                  ? "danger"
                  : voice.speaker?.verified
                    ? "success"
                    : undefined
            }
          />
          <Row
            label={t("deck.wakeWord")}
            value={config?.voice.wake_word_model || "—"}
            tone={config ? undefined : "muted"}
          />
          {voice.error && <p className={cn(s.note, s.danger)}>{voice.error}</p>}
        </Pane>
      </div>

      {/* ---------------- centre: the orb ---------------- */}
      <div className={s.stage}>
        <div className={s.orbWrap}>
          <LiveOrb state={voice.state} registerLevelSink={registerLevelSink} />
        </div>

        <div className={s.stageState}>{t(PIPELINE_KEY[voice.state])}</div>

        <div className={s.transcript}>
          {voice.state === "speaking" && voice.speech?.text ? (
            <>
              <span className={s.transcriptLabel}>{t("deck.speakingNow")}</span>
              <p className={s.transcriptText}>{voice.speech.text}</p>
            </>
          ) : voice.transcript?.text ? (
            <>
              <span className={s.transcriptLabel}>{t("deck.lastTranscript")}</span>
              <p className={s.transcriptText}>{voice.transcript.text}</p>
            </>
          ) : lastAssistant ? (
            <>
              <span className={s.transcriptLabel}>{t("deck.lastResponse")}</span>
              <p className={s.transcriptText}>{lastAssistant.content.slice(0, 240)}</p>
            </>
          ) : (
            <p className={cn(s.transcriptText, s.muted)}>
              {t("deck.prompt")}
            </p>
          )}
        </div>

        <NowPlaying />

        <form className={s.commandBar} onSubmit={submit}>
          <input
            className={s.commandInput}
            value={draft}
            placeholder={
              chat.status === "open" ? t("deck.commandPlaceholder") : t("common.connecting")
            }
            spellCheck={false}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button
            type="submit"
            className={s.send}
            disabled={!draft.trim() || chat.status !== "open"}
            aria-label={t("deck.send")}
          >
            <SendIcon />
          </button>
        </form>
      </div>

      {/* ---------------- right: the assistant ---------------- */}
      <div className={s.column}>
        <Pane
          title={t("route.mcp")}
          meta={`${connectedServers}/${servers.length} · ${status?.mcp_tools ?? 0} ${t("deck.toolsAbbr")}`}
        >
          {servers.length === 0 ? (
            <p className={s.note}>{t("deck.noServers")}</p>
          ) : (
            servers.map((server) => (
              <div key={server.name} className={s.row}>
                <span className={s.rowLabel}>
                  <span
                    className={cn(
                      s.led,
                      server.connected
                        ? s.ledOk
                        : server.enabled
                          ? s.ledBad
                          : s.ledOff,
                    )}
                  />
                  {server.name}
                </span>
                <span className={s.rowValue}>{server.tool_count}</span>
              </div>
            ))
          )}
        </Pane>

        <Pane title={t("deck.tools")} meta={t("deck.latency")}>
          {runs.length === 0 && audit.length === 0 ? (
            <p className={s.note}>{t("deck.nothingRun")}</p>
          ) : runs.length > 0 ? (
            runs.map((run) => (
              <div key={run.id} className={s.row}>
                <span className={s.rowLabel}>
                  <span
                    className={cn(
                      s.led,
                      run.elapsedMs === null
                        ? s.ledLive
                        : run.error
                          ? s.ledBad
                          : s.ledOk,
                    )}
                  />
                  {run.server && (
                    <span
                      className={cn(
                        s.toolServer,
                        run.elapsedMs === null ? s.toolServerRunning : s.toolServerDone,
                      )}
                    >
                      {run.server}
                    </span>
                  )}
                  <span className={s.toolName}>{run.tool}</span>
                </span>
                <span className={s.rowValue}>
                  {run.elapsedMs === null ? "···" : `${run.elapsedMs} ms`}
                </span>
              </div>
            ))
          ) : (
            audit.slice(0, 6).map((entry, i) => (
              <div key={`${entry.timestamp}-${i}`} className={s.row}>
                <span className={s.rowLabel}>
                  <span
                    className={cn(
                      s.led,
                      entry.status === "success" ? s.ledOk : s.ledBad,
                    )}
                  />
                  {entry.server_name && (
                    <span
                      className={cn(
                        s.toolServer,
                        entry.status === "success" ? s.toolServerDone : s.danger,
                      )}
                    >
                      {entry.server_name}
                    </span>
                  )}
                  <span className={s.toolName}>{entry.tool_name}</span>
                </span>
                <span className={s.rowValue}>
                  {new Date(entry.timestamp).toLocaleTimeString(intlLocale, {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
            ))
          )}
        </Pane>

        {/* Always present, deliberately quiet. */}
        <Pane title={t("route.logs")} className={s.logPane} meta={`${logs.length}`}>
          <div className={s.logTail}>
            {tail.length === 0 ? (
              <p className={s.note}>{t("deck.noActivity")}</p>
            ) : (
              tail.map((line) => (
                <button
                  key={line.id}
                  type="button"
                  className={cn(s.logLine, expandedLogId === line.id && s.logLineExpanded)}
                  aria-expanded={expandedLogId === line.id}
                  onClick={() =>
                    setExpandedLogId((current) => current === line.id ? null : line.id)
                  }
                >
                  <span
                    className={cn(
                      s.logLevel,
                      line.level === "ERROR" || line.level === "CRITICAL"
                        ? s.danger
                        : line.level === "WARNING"
                          ? s.warning
                          : undefined,
                    )}
                  >
                    {line.level.slice(0, 4).toLowerCase()}
                  </span>
                  <span className={s.logMessage}>{line.message}</span>
                </button>
              ))
            )}
          </div>
        </Pane>
      </div>
    </div>
  );
}
