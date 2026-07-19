import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "../api/client";
import { getBaseUrl } from "../api/connection";
import type {
  MCPServerStatus,
  StatusResponse,
  ToolAuditEntry,
} from "../api/types";
import {
  Badge,
  Button,
  Panel,
  PanelHeader,
  Spinner,
  Toggle,
  useToast,
} from "../design/primitives";
import s from "./Dashboard.module.css";
import { useI18n } from "../i18n/I18n";

/**
 * Read-only status overview. Its job in M1 is to prove the HTTP client,
 * bearer auth, and the design system work end to end against a live backend.
 */
export function Dashboard({ onUnauthorized }: { onUnauthorized: () => void }) {
  const { intlLocale, t } = useI18n();
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [servers, setServers] = useState<MCPServerStatus[]>([]);
  const [audit, setAudit] = useState<ToolAuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, nextServers, nextAudit] = await Promise.all([
        api.status(),
        api.mcpStatus(),
        // The audit log is supplementary — a failure here must not blank the
        // whole dashboard.
        api.toolAudit(20).catch(() => [] as ToolAuditEntry[]),
      ]);
      setStatus(nextStatus);
      setServers(nextServers);
      setAudit(nextAudit);
      setError(null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        onUnauthorized();
        return;
      }
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [onUnauthorized]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function toggleVoice(next: boolean) {
    try {
      const result = await api.toggleVoice(next);
      setStatus((prev) =>
        prev ? { ...prev, voice_listening: result.voice_listening } : prev,
      );
    } catch (err) {
      toast.show(err instanceof Error ? err.message : String(err), "danger");
    }
  }

  if (loading && !status) {
    return (
      <div className={s.empty}>
        <Spinner size={18} />
      </div>
    );
  }

  const connected = servers.filter((server) => server.connected).length;

  return (
    <>
      <div className={s.header}>
        <div>
          <div className={s.title}>{t("dashboard.title")}</div>
          <div className={s.subtitle}>{getBaseUrl()}</div>
        </div>
        <Button size="sm" onClick={() => void refresh()}>
          {t("common.refresh")}
        </Button>
      </div>

      {error && <div className={s.error}>{error}</div>}

      {status && (
        <div className={s.grid}>
          <div className={s.stat}>
            <div className={s.statLabel}>{t("dashboard.status")}</div>
            <div className={s.statValue}>{status.status}</div>
            <div className={s.statMeta}>
              {status.name} v{status.version}
            </div>
          </div>

          <div className={s.stat}>
            <div className={s.statLabel}>{t("dashboard.provider")}</div>
            <div className={s.statValue}>{status.llm_provider}</div>
            <div className={s.statMeta}>{t("dashboard.routerDefault")}</div>
          </div>

          <div className={s.stat}>
            <div className={s.statLabel}>MCP</div>
            <div className={s.statValue}>{status.mcp_tools}</div>
            <div className={s.statMeta}>
              {t("dashboard.toolsAcross", { tools: status.mcp_tools, servers: status.mcp_servers })}
            </div>
          </div>

          <div className={s.stat}>
            <div className={s.statLabel}>{t("dashboard.voice")}</div>
            <div className={s.statValue}>
              {status.voice_listening ? t("deck.listening") : t("deck.idle")}
            </div>
            <div className={s.statMeta}>
              <Toggle
                checked={status.voice_listening}
                onChange={(next) => void toggleVoice(next)}
                aria-label={t("dashboard.toggleVoice")}
              />
            </div>
          </div>
        </div>
      )}

      <Panel>
        <PanelHeader
          title={t("dashboard.mcpServers")}
          subtitle={t("dashboard.connectedCount", { connected, total: servers.length })}
        />
        {servers.length === 0 ? (
          <div className={s.empty}>{t("dashboard.noServers")}</div>
        ) : (
          servers.map((server) => (
            <div key={server.name} className={s.serverRow}>
              <div>
                <div className={s.serverName}>{server.name}</div>
                <div className={s.serverMeta}>
                  {server.transport} · {t("chat.toolsCount", { count: server.tool_count })}
                </div>
              </div>
              <div className={s.right}>
                {!server.enabled && <Badge tone="neutral">{t("dashboard.disabled")}</Badge>}
                <Badge tone={server.connected ? "success" : "danger"} dot>
                  {server.connected ? t("common.connected") : t("common.offline")}
                </Badge>
              </div>
            </div>
          ))
        )}
      </Panel>

      <Panel>
        <PanelHeader
          title={t("dashboard.recentTools")}
          subtitle={t("dashboard.lastExecutions", { count: audit.length })}
        />
        {audit.length === 0 ? (
          <div className={s.empty}>{t("dashboard.noTools")}</div>
        ) : (
          audit.map((entry, i) => (
            <div key={`${entry.timestamp}-${i}`} className={s.serverRow}>
              <div>
                <div className={s.serverName}>{entry.tool_name}</div>
                <div className={s.serverMeta}>
                  {entry.server_name} · {new Date(entry.timestamp).toLocaleTimeString(intlLocale)}
                </div>
              </div>
              <div className={s.right}>
                <Badge
                  tone={
                    entry.status === "success"
                      ? "success"
                      : entry.status === "denied"
                        ? "warning"
                        : "danger"
                  }
                >
                  {entry.status}
                </Badge>
              </div>
            </div>
          ))
        )}
      </Panel>
    </>
  );
}
