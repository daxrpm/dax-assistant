import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { FullConfig, MCPServerConfig, MCPServerStatus } from "../api/types";
import {
  CheckIcon,
  PlusIcon,
  RefreshIcon,
  SettingsIcon,
  TrashIcon,
} from "./icons";
import {
  Badge,
  Button,
  Checkbox,
  Field,
  IconButton,
  Modal,
  Panel,
  PanelBody,
  PanelHeader,
  Select,
  TextArea,
  TextInput,
  Toggle,
  useToast,
} from "../design/primitives";
import p from "../screens/page.module.css";
import s from "./McpServers.module.css";

/* ---------------- text ↔ dict helpers (ported from web/McpTab.tsx) ---------------- */

function parseEnv(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    out[trimmed.slice(0, eq).trim()] = trimmed.slice(eq + 1).trim();
  }
  return out;
}

function parseHeaders(text: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const colon = trimmed.indexOf(":");
    if (colon === -1) continue;
    out[trimmed.slice(0, colon).trim()] = trimmed.slice(colon + 1).trim();
  }
  return out;
}

function envToText(env: Record<string, string> | undefined): string {
  return Object.entries(env ?? {})
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");
}

function headersToText(headers: Record<string, string> | undefined): string {
  return Object.entries(headers ?? {})
    .map(([k, v]) => `${k}: ${v}`)
    .join("\n");
}

/* ---------------- add / edit form ---------------- */

export interface ServerDraft {
  name: string;
  transport: string;
  command: string;
  args: string;
  url: string;
  env: string;
  headers: string;
  enabled: boolean;
  export_codex: boolean;
  export_claude: boolean;
}

export function emptyDraft(): ServerDraft {
  return {
    name: "",
    transport: "stdio",
    command: "",
    args: "",
    url: "",
    env: "",
    headers: "",
    enabled: true,
    export_codex: false,
    export_claude: false,
  };
}

function draftFromConfig(name: string, cfg: MCPServerConfig): ServerDraft {
  return {
    name,
    transport: cfg.transport || "stdio",
    command: cfg.command ?? "",
    args: (cfg.args ?? []).join(" "),
    url: cfg.url ?? "",
    env: envToText(cfg.env),
    headers: headersToText(cfg.headers),
    enabled: cfg.enabled,
    export_codex: cfg.export_codex,
    export_claude: cfg.export_claude,
  };
}

function draftToPayload(draft: ServerDraft): Record<string, unknown> {
  return {
    name: draft.name.trim(),
    transport: draft.transport,
    command: draft.command.trim(),
    args: draft.args.split(/\s+/).filter(Boolean),
    url: draft.url.trim(),
    env: parseEnv(draft.env),
    headers: parseHeaders(draft.headers),
    enabled: draft.enabled,
    export_codex: draft.export_codex,
    export_claude: draft.export_claude,
  };
}

function ServerForm({
  draft,
  setDraft,
  editing,
}: {
  draft: ServerDraft;
  setDraft: (next: ServerDraft) => void;
  editing: boolean;
}) {
  const http = draft.transport !== "stdio";
  const set = <K extends keyof ServerDraft>(key: K, value: ServerDraft[K]) =>
    setDraft({ ...draft, [key]: value });

  return (
    <div className={p.stack}>
      <div className={p.row2}>
        <Field label="Name">
          {(id) => (
            <TextInput
              id={id}
              value={draft.name}
              disabled={editing}
              placeholder="nextcloud"
              onChange={(e) => set("name", e.target.value)}
            />
          )}
        </Field>
        <Field label="Transport">
          {(id) => (
            <Select
              id={id}
              value={draft.transport}
              onChange={(e) => set("transport", e.target.value)}
            >
              <option value="stdio">stdio (subprocess)</option>
              <option value="http">streamable HTTP</option>
            </Select>
          )}
        </Field>
      </div>

      {http ? (
        <>
          <Field label="URL">
            {(id) => (
              <TextInput
                id={id}
                value={draft.url}
                placeholder="https://example.com/mcp"
                onChange={(e) => set("url", e.target.value)}
              />
            )}
          </Field>
          <Field
            label="Headers"
            description="One per line, `Name: value`. Stored encrypted — leave a masked value untouched to keep it."
          >
            {(id) => (
              <TextArea
                id={id}
                rows={3}
                value={draft.headers}
                placeholder="Authorization: Bearer abc123"
                onChange={(e) => set("headers", e.target.value)}
              />
            )}
          </Field>
        </>
      ) : (
        <>
          <Field label="Command">
            {(id) => (
              <TextInput
                id={id}
                value={draft.command}
                placeholder="uvx"
                onChange={(e) => set("command", e.target.value)}
              />
            )}
          </Field>
          <Field label="Arguments" description="Space separated.">
            {(id) => (
              <TextInput
                id={id}
                value={draft.args}
                placeholder="nextcloud-mcp-server@latest"
                onChange={(e) => set("args", e.target.value)}
              />
            )}
          </Field>
        </>
      )}

      <Field
        label="Environment"
        description="One per line, `KEY=value`. Every value is stored encrypted."
      >
        {(id) => (
          <TextArea
            id={id}
            rows={3}
            value={draft.env}
            placeholder="API_TOKEN=…"
            onChange={(e) => set("env", e.target.value)}
          />
        )}
      </Field>

      <div className={p.actions}>
        <Checkbox
          checked={draft.enabled}
          onChange={(v) => set("enabled", v)}
          label="Enabled"
        />
        <Checkbox
          checked={draft.export_codex}
          onChange={(v) => set("export_codex", v)}
          label="Export to Codex"
        />
        <Checkbox
          checked={draft.export_claude}
          onChange={(v) => set("export_claude", v)}
          label="Export to Claude"
        />
      </div>
    </div>
  );
}

/* ---------------- OAuth control ---------------- */

/**
 * OAuth for a remote server.
 *
 * The callback returns to the *backend*, not to us (PLAN.md 4.2), so the flow
 * is: open the authorization URL in the system browser, then poll
 * `/auth/status` until it flips. Intercepting the redirect in the webview is
 * explicitly not an option.
 */
function OAuthControl({ name }: { name: string }) {
  const toast = useToast();
  const [status, setStatus] = useState<{ authenticated: boolean; expired?: boolean } | null>(
    null,
  );
  const [polling, setPolling] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.mcpAuthStatus(name));
    } catch {
      setStatus(null);
    }
  }, [name]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const start = async () => {
    try {
      const { authorization_url } = await api.startMcpAuth(name);
      const { openUrl } = await import("@tauri-apps/plugin-opener");
      await openUrl(authorization_url);
      toast.show("Finish signing in in your browser", "neutral");

      // Poll until the backend records the token. Capped so a user who
      // abandons the browser tab does not leave a timer running forever.
      setPolling(true);
      let attempts = 0;
      const timer = setInterval(() => {
        attempts += 1;
        void api
          .mcpAuthStatus(name)
          .then((next) => {
            setStatus(next);
            if (next.authenticated) {
              clearInterval(timer);
              setPolling(false);
              toast.show(`${name} authenticated`, "success");
            }
          })
          .catch(() => {
            /* keep polling */
          });
        if (attempts >= 60) {
          clearInterval(timer);
          setPolling(false);
        }
      }, 2000);
    } catch (err) {
      setPolling(false);
      toast.show(err instanceof Error ? err.message : "OAuth failed", "danger");
    }
  };

  if (!status) return null;

  if (status.authenticated && !status.expired) {
    return (
      <div className={p.actions}>
        <Badge tone="success" dot>
          Authenticated
        </Badge>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            void api
              .logoutMcp(name)
              .then(refresh)
              .catch(() => toast.show("Sign out failed", "danger"));
          }}
        >
          Sign out
        </Button>
      </div>
    );
  }

  return (
    <div className={p.actions}>
      {status.expired && <Badge tone="warning">Token expired</Badge>}
      <Button size="sm" variant="secondary" loading={polling} onClick={() => void start()}>
        {polling ? "Waiting for browser…" : "Authenticate"}
      </Button>
    </div>
  );
}

/* ---------------- server table ---------------- */

export function McpServers({
  config,
  onSaved,
  prefill,
  onPrefillConsumed,
}: {
  config: FullConfig;
  onSaved: () => void;
  /** Set by the Marketplace install flow to open the form pre-populated. */
  prefill?: ServerDraft | null;
  onPrefillConsumed?: () => void;
}) {
  const toast = useToast();
  const [statuses, setStatuses] = useState<MCPServerStatus[]>([]);
  const [draft, setDraft] = useState<ServerDraft | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const loadStatuses = useCallback(() => {
    api
      .mcpStatus()
      .then(setStatuses)
      .catch(() => setStatuses([]));
  }, []);

  useEffect(loadStatuses, [loadStatuses]);

  useEffect(() => {
    if (prefill) {
      setDraft(prefill);
      setEditing(false);
      onPrefillConsumed?.();
    }
  }, [prefill, onPrefillConsumed]);

  const servers = Object.entries(config.mcp.servers);

  const save = async () => {
    if (!draft || !draft.name.trim()) return;
    setBusy(draft.name);
    try {
      const payload = draftToPayload(draft);
      if (editing) {
        await api.updateMcpServer(draft.name, payload);
      } else {
        await api.addMcpServer(payload);
      }
      toast.show(`${draft.name} saved`, "success");
      setDraft(null);
      onSaved();
      loadStatuses();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Save failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  const reconnect = async (name: string) => {
    setBusy(name);
    try {
      const result = await api.reconnectMcpServer(name);
      toast.show(`${name}: ${result.tools} tools`, "success");
      loadStatuses();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Reconnect failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (name: string) => {
    setBusy(name);
    try {
      await api.deleteMcpServer(name);
      toast.show(`${name} removed`, "success");
      onSaved();
      loadStatuses();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Delete failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  const toggleEnabled = async (name: string, cfg: MCPServerConfig, enabled: boolean) => {
    setBusy(name);
    try {
      await api.updateMcpServer(name, { ...cfg, enabled });
      onSaved();
      loadStatuses();
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Update failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Servers"
        subtitle={`${servers.length} configured`}
        actions={
          <Button
            size="sm"
            variant="primary"
            onClick={() => {
              setDraft(emptyDraft());
              setEditing(false);
            }}
          >
            <PlusIcon size={13} />
            Add server
          </Button>
        }
      />
      <PanelBody>
        {servers.length === 0 && (
          <p className={p.hint}>No MCP servers yet. Add one, or install from the Marketplace.</p>
        )}

        <div className={s.table}>
          {servers.map(([name, cfg]) => {
            const status = statuses.find((st) => st.name === name);
            const isOpen = expanded === name;
            return (
              <div key={name} className={s.serverRow}>
                <div className={s.serverMain}>
                  <button
                    type="button"
                    className={s.serverName}
                    onClick={() => setExpanded(isOpen ? null : name)}
                  >
                    {name}
                  </button>
                  <Badge tone={status?.connected ? "success" : "neutral"} dot>
                    {status?.connected ? "Connected" : "Offline"}
                  </Badge>
                  <span className={s.serverMeta}>{cfg.transport}</span>
                  <span className={s.serverMeta}>
                    {status?.tool_count ?? 0} tool{(status?.tool_count ?? 0) !== 1 ? "s" : ""}
                  </span>

                  <div className={s.serverActions}>
                    <Toggle
                      checked={cfg.enabled}
                      onChange={(v) => void toggleEnabled(name, cfg, v)}
                      disabled={busy === name}
                      aria-label={`Enable ${name}`}
                    />
                    <IconButton
                      label={`Reconnect ${name}`}
                      disabled={busy === name}
                      onClick={() => void reconnect(name)}
                    >
                      <RefreshIcon size={13} />
                    </IconButton>
                    <IconButton
                      label={`Edit ${name}`}
                      onClick={() => {
                        setDraft(draftFromConfig(name, cfg));
                        setEditing(true);
                      }}
                    >
                      <SettingsIcon size={13} />
                    </IconButton>
                    <IconButton
                      label={`Delete ${name}`}
                      danger
                      disabled={busy === name}
                      onClick={() => void remove(name)}
                    >
                      <TrashIcon size={13} />
                    </IconButton>
                  </div>
                </div>

                {isOpen && (
                  <div className={s.serverDetail}>
                    {cfg.transport !== "stdio" && <OAuthControl name={name} />}
                    <div className={s.serverCmd}>
                      {cfg.transport === "stdio"
                        ? `${cfg.command} ${(cfg.args ?? []).join(" ")}`
                        : cfg.url}
                    </div>
                    {(status?.tools?.length ?? 0) > 0 && (
                      <div className={p.tagList}>
                        {status?.tools.map((tool) => (
                          <span key={tool} className={p.tag}>
                            {tool}
                          </span>
                        ))}
                      </div>
                    )}
                    <div className={p.actions}>
                      {cfg.export_codex && <Badge tone="accent">Codex export</Badge>}
                      {cfg.export_claude && <Badge tone="accent">Claude export</Badge>}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </PanelBody>

      <Modal
        open={draft !== null}
        wide
        title={editing ? `Edit ${draft?.name}` : "Add MCP server"}
        onClose={() => setDraft(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDraft(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              loading={busy !== null}
              disabled={!draft?.name.trim()}
              onClick={() => void save()}
            >
              <CheckIcon size={13} />
              Save
            </Button>
          </>
        }
      >
        {draft && <ServerForm draft={draft} setDraft={setDraft} editing={editing} />}
      </Modal>
    </Panel>
  );
}
