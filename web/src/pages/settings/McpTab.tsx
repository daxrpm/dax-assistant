import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { RefreshCw, Trash2, Plus, CheckCircle2, XCircle, Pencil, ChevronDown, ChevronRight } from "lucide-react";
import { api, type MCPServerStatus } from "../../api/client";
import type { FullConfig, MCPServerConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  TextArea,
  Select,
  Badge,
  Modal,
  Toggle,
  useToast,
} from "../../components/ui";

// ---------- text ↔ dict helpers ----------

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

// ---------- main tab ----------

export function McpTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [status, setStatus] = useState<MCPServerStatus[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<{ name: string; srv: MCPServerConfig } | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const toggleExpanded = (name: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });

  const refreshStatus = () =>
    api.getMCPStatus().then(setStatus).catch(() => setStatus([]));

  useEffect(() => {
    refreshStatus();
  }, [config]);

  const reconnect = async (name: string) => {
    setBusy(name);
    try {
      const res = await api.reconnectMCPServer(name);
      toast.show(`${name}: ${res.tools} tools`, "success");
      await refreshStatus();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Reconnect failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  const remove = async (name: string) => {
    setBusy(name);
    try {
      await api.deleteMCPServer(name);
      toast.show(`Removed ${name}`, "success");
      onSaved();
      await refreshStatus();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Delete failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  const servers = Object.entries(config.mcp.servers);
  const statusOf = (name: string) => status.find((s) => s.name === name);

  return (
    <Panel>
      <PanelHeader
        title="MCP servers"
        description="Tool providers connected over stdio or HTTP"
        action={
          <Button variant="primary" size="sm" onPress={() => setAdding(true)}>
            <Plus size={15} />
            Add
          </Button>
        }
      />

      <div className="flex flex-col gap-2">
        {servers.length === 0 && (
          <p className="text-sm text-muted">No MCP servers configured.</p>
        )}
        {servers.map(([name, srv]) => {
          const st = statusOf(name);
          const connected = st?.connected ?? false;
          const tools = st?.tools ?? [];
          const isExpanded = expanded.has(name);
          return (
            <div
              key={name}
              className="rounded-xl border border-separator bg-background px-3 py-3"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex min-w-0 items-center gap-2">
                  {connected ? (
                    <CheckCircle2 size={16} className="text-success" />
                  ) : (
                    <XCircle size={16} className="text-danger" />
                  )}
                  <span className="truncate text-sm font-medium">{name}</span>
                  <Badge>{srv.transport}</Badge>
                  {st && (
                    <button
                      className="flex items-center gap-1 rounded px-1 hover:bg-accent-soft transition-colors"
                      onClick={() => tools.length > 0 && toggleExpanded(name)}
                      title={tools.length > 0 ? "Show tools" : undefined}
                    >
                      <Badge color={connected ? "success" : "default"}>
                        {st.tool_count} tools
                      </Badge>
                      {tools.length > 0 && (
                        isExpanded
                          ? <ChevronDown size={12} className="text-muted" />
                          : <ChevronRight size={12} className="text-muted" />
                      )}
                    </button>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <Button
                    variant="tertiary"
                    size="sm"
                    isIconOnly
                    isDisabled={busy === name}
                    onPress={() => setEditing({ name, srv })}
                    aria-label="Edit"
                  >
                    <Pencil size={15} />
                  </Button>
                  <Button
                    variant="tertiary"
                    size="sm"
                    isIconOnly
                    isDisabled={busy === name}
                    onPress={() => reconnect(name)}
                    aria-label="Reconnect"
                  >
                    <RefreshCw size={15} />
                  </Button>
                  <Button
                    variant="tertiary"
                    size="sm"
                    isIconOnly
                    isDisabled={busy === name}
                    onPress={() => remove(name)}
                    aria-label="Remove"
                  >
                    <Trash2 size={15} className="text-danger" />
                  </Button>
                </div>
              </div>
              <p className="mt-1 truncate pl-6 font-mono text-xs text-muted">
                {srv.transport === "stdio"
                  ? `${srv.command} ${srv.args.join(" ")}`
                  : srv.url}
              </p>
              {isExpanded && tools.length > 0 && (
                <div className="mt-2 pl-6">
                  <div className="flex flex-wrap gap-1">
                    {tools.map((tool) => (
                      <span
                        key={tool}
                        className="rounded-md bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent"
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <ServerFormModal
        mode="add"
        open={adding}
        onClose={() => setAdding(false)}
        onDone={async () => {
          setAdding(false);
          onSaved();
          await refreshStatus();
        }}
      />

      {editing && (
        <ServerFormModal
          mode="edit"
          serverName={editing.name}
          initial={editing.srv}
          open
          onClose={() => setEditing(null)}
          onDone={async () => {
            setEditing(null);
            onSaved();
            await refreshStatus();
          }}
        />
      )}
    </Panel>
  );
}

// ---------- shared form modal ----------

type FormMode = "add" | "edit";

function ServerFormModal({
  mode,
  serverName,
  initial,
  open,
  onClose,
  onDone,
}: {
  mode: FormMode;
  serverName?: string;
  initial?: MCPServerConfig;
  open: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(serverName ?? "");
  const [transport, setTransport] = useState(initial?.transport ?? "stdio");
  const [command, setCommand] = useState(initial?.command ?? "");
  const [args, setArgs] = useState(initial?.args.join(" ") ?? "");
  const [url, setUrl] = useState(initial?.url ?? "");
  const [env, setEnv] = useState(initial ? envToText(initial.env) : "");
  const [headers, setHeaders] = useState(initial ? headersToText(initial.headers) : "");
  const [exportCodex, setExportCodex] = useState(initial?.export_codex ?? false);
  const [exportClaude, setExportClaude] = useState(initial?.export_claude ?? false);
  const [saving, setSaving] = useState(false);

  // Re-sync when switching between edit targets
  useEffect(() => {
    setName(serverName ?? "");
    setTransport(initial?.transport ?? "stdio");
    setCommand(initial?.command ?? "");
    setArgs(initial?.args.join(" ") ?? "");
    setUrl(initial?.url ?? "");
    setEnv(initial ? envToText(initial.env) : "");
    setHeaders(initial ? headersToText(initial.headers) : "");
    setExportCodex(initial?.export_codex ?? false);
    setExportClaude(initial?.export_claude ?? false);
  }, [serverName, initial]);

  const buildPayload = () => ({
    transport,
    command: transport === "stdio" ? command.trim() : "",
    args: transport === "stdio" ? args.split(" ").map((a) => a.trim()).filter(Boolean) : [],
    url: transport !== "stdio" ? url.trim() : "",
    env: parseEnv(env),
    headers: transport !== "stdio" ? parseHeaders(headers) : {},
    enabled: true,
    export_codex: exportCodex,
    export_claude: exportClaude,
  });

  const submit = async () => {
    if (mode === "add" && !name.trim()) {
      toast.show("Name is required", "warning");
      return;
    }
    setSaving(true);
    try {
      if (mode === "add") {
        await api.addMCPServer({ name: name.trim(), ...buildPayload() });
        toast.show(`Added ${name.trim()}`, "success");
      } else {
        await api.updateMCPServer(serverName!, buildPayload());
        toast.show(`Saved ${serverName}`, "success");
      }
      onDone();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : `${mode === "add" ? "Add" : "Save"} failed`, "danger");
    } finally {
      setSaving(false);
    }
  };

  const title = mode === "add" ? "Add MCP server" : `Edit — ${serverName}`;
  const submitLabel = saving
    ? mode === "add" ? "Adding…" : "Saving…"
    : mode === "add" ? "Add" : "Save";

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="tertiary" onPress={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onPress={submit} isDisabled={saving}>
            {submitLabel}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {mode === "add" && (
          <Field label="Name">
            <TextInput
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="filesystem"
            />
          </Field>
        )}
        <Field label="Transport">
          <Select value={transport} onChange={(e) => setTransport(e.target.value)}>
            <option value="stdio">stdio (local process)</option>
            <option value="streamable_http">Streamable HTTP (remote)</option>
          </Select>
        </Field>
        {transport === "stdio" ? (
          <>
            <Field label="Command">
              <TextInput
                value={command}
                onChange={(e) => setCommand(e.target.value)}
                placeholder="npx"
              />
            </Field>
            <Field label="Arguments" description="Space-separated">
              <TextInput
                value={args}
                onChange={(e) => setArgs(e.target.value)}
                placeholder="-y @modelcontextprotocol/server-filesystem /home"
              />
            </Field>
          </>
        ) : (
          <>
            <Field label="URL">
              <TextInput
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://coolify.dax.dev/mcp"
              />
            </Field>
            <Field
              label="HTTP headers"
              description='One "Key: value" per line. Use {env:NAME} for secrets.'
            >
              <TextArea
                rows={3}
                value={headers}
                onChange={(e) => setHeaders(e.target.value)}
                placeholder={"Authorization: Bearer {env:COOLIFY_TOKEN}\nX-Custom-Header: value"}
              />
            </Field>
          </>
        )}
        <Field
          label="Environment variables"
          description="One KEY=value per line. Use {env:NAME} to read from .env."
        >
          <TextArea
            rows={3}
            value={env}
            onChange={(e) => setEnv(e.target.value)}
            placeholder={"NEXTCLOUD_HOST=https://cloud.example.com\nNEXTCLOUD_PASSWORD={env:NEXTCLOUD_PASSWORD}"}
          />
        </Field>

        {/* Export this server to external AI clients */}
        <div className="flex flex-col gap-2 rounded-xl border border-separator bg-background p-3">
          <p className="text-xs font-medium text-muted">
            Share this server with external AI clients
          </p>
          <label className="flex cursor-pointer items-center justify-between">
            <span className="text-sm">Include in Codex config</span>
            <Toggle checked={exportCodex} onChange={setExportCodex} label="Export to Codex" />
          </label>
          <label className="flex cursor-pointer items-center justify-between">
            <span className="text-sm">Include in Claude config</span>
            <Toggle checked={exportClaude} onChange={setExportClaude} label="Export to Claude" />
          </label>
        </div>
      </div>
    </Modal>
  );
}
