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

/**
 * Read-only status overview. Its job in M1 is to prove the HTTP client,
 * bearer auth, and the design system work end to end against a live backend.
 */
export function Dashboard({ onUnauthorized }: { onUnauthorized: () => void }) {
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
          <div className={s.title}>Dashboard</div>
          <div className={s.subtitle}>{getBaseUrl()}</div>
        </div>
        <Button size="sm" onClick={() => void refresh()}>
          Refresh
        </Button>
      </div>

      {error && <div className={s.error}>{error}</div>}

      {status && (
        <div className={s.grid}>
          <div className={s.stat}>
            <div className={s.statLabel}>Status</div>
            <div className={s.statValue}>{status.status}</div>
            <div className={s.statMeta}>
              {status.name} v{status.version}
            </div>
          </div>

          <div className={s.stat}>
            <div className={s.statLabel}>LLM provider</div>
            <div className={s.statValue}>{status.llm_provider}</div>
            <div className={s.statMeta}>Active router default</div>
          </div>

          <div className={s.stat}>
            <div className={s.statLabel}>MCP</div>
            <div className={s.statValue}>{status.mcp_tools}</div>
            <div className={s.statMeta}>
              tools across {status.mcp_servers} server
              {status.mcp_servers === 1 ? "" : "s"}
            </div>
          </div>

          <div className={s.stat}>
            <div className={s.statLabel}>Voice</div>
            <div className={s.statValue}>
              {status.voice_listening ? "Listening" : "Idle"}
            </div>
            <div className={s.statMeta}>
              <Toggle
                checked={status.voice_listening}
                onChange={(next) => void toggleVoice(next)}
                aria-label="Toggle voice listening"
              />
            </div>
          </div>
        </div>
      )}

      <Panel>
        <PanelHeader
          title="MCP servers"
          subtitle={`${connected} of ${servers.length} connected`}
        />
        {servers.length === 0 ? (
          <div className={s.empty}>No MCP servers configured.</div>
        ) : (
          servers.map((server) => (
            <div key={server.name} className={s.serverRow}>
              <div>
                <div className={s.serverName}>{server.name}</div>
                <div className={s.serverMeta}>
                  {server.transport} · {server.tool_count} tool
                  {server.tool_count === 1 ? "" : "s"}
                </div>
              </div>
              <div className={s.right}>
                {!server.enabled && <Badge tone="neutral">Disabled</Badge>}
                <Badge tone={server.connected ? "success" : "danger"} dot>
                  {server.connected ? "Connected" : "Offline"}
                </Badge>
              </div>
            </div>
          ))
        )}
      </Panel>

      <Panel>
        <PanelHeader
          title="Recent tool activity"
          subtitle={`Last ${audit.length} execution${audit.length === 1 ? "" : "s"}`}
        />
        {audit.length === 0 ? (
          <div className={s.empty}>No tools have run yet.</div>
        ) : (
          audit.map((entry, i) => (
            <div key={`${entry.timestamp}-${i}`} className={s.serverRow}>
              <div>
                <div className={s.serverName}>{entry.tool_name}</div>
                <div className={s.serverMeta}>
                  {entry.server_name} · {new Date(entry.timestamp).toLocaleTimeString()}
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
