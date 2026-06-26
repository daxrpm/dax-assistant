import { useEffect, useMemo, useState } from "react";
import { Button } from "@heroui/react";
import {
  RefreshCw,
  Trash2,
  Plus,
  Check,
  CheckCircle2,
  XCircle,
  Pencil,
  ChevronDown,
  ChevronRight,
  Download,
  Globe,
  Loader2,
  Package,
  Search,
  Sparkles,
} from "lucide-react";
import { api, type MCPServerStatus, type MCPPreset, type RegistryServer } from "../../api/client";
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
  const [presets, setPresets] = useState<MCPPreset[]>([]);
  const [registryQuery, setRegistryQuery] = useState("");
  const [registryResults, setRegistryResults] = useState<RegistryServer[]>([]);
  const [registryLoading, setRegistryLoading] = useState(false);
  const [installing, setInstalling] = useState<string | null>(null);
  const [installView, setInstallView] = useState<"presets" | "registry">("presets");

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

  useEffect(() => {
    api.getMCPPresets().then(setPresets).catch(() => setPresets([]));
  }, []);

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

  const setExportFlag = async (
    name: string,
    srv: MCPServerConfig,
    key: "export_codex" | "export_claude",
    value: boolean,
  ) => {
    setBusy(`${name}:${key}`);
    try {
      await api.updateMCPServer(name, { ...srv, [key]: value });
      toast.show(`${name}: ${key === "export_codex" ? "Codex" : "Claude"} export ${value ? "enabled" : "disabled"}`, "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Export update failed", "danger");
    } finally {
      setBusy(null);
    }
  };

  const servers = Object.entries(config.mcp.servers);
  const installed = useMemo(() => new Set(servers.map(([name]) => name)), [servers]);
  const statusOf = (name: string) => status.find((s) => s.name === name);

  const installPreset = async (preset: MCPPreset) => {
    setInstalling(preset.id);
    try {
      await api.addMCPServer({
        name: preset.id,
        command: preset.command,
        args: preset.args,
        env: preset.env,
        transport: preset.transport,
        enabled: true,
      });
      toast.show(`${preset.name} installed`, "success");
      onSaved();
      await refreshStatus();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Install failed", "danger");
    } finally {
      setInstalling(null);
    }
  };

  const searchRegistry = async () => {
    setRegistryLoading(true);
    try {
      const { servers, error } = await api.searchMCPRegistry(registryQuery, 40);
      if (error) toast.show(`Registry: ${error}`, "warning");
      setRegistryResults(servers);
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Search failed", "danger");
    } finally {
      setRegistryLoading(false);
    }
  };

  const installRegistry = async (server: RegistryServer) => {
    const id = (server.name.split("/").pop() ?? server.name).replace(/[^a-zA-Z0-9_-]/g, "-");
    setInstalling(server.name);
    try {
      const pkg = server.packages[0];
      const remote = server.remotes[0];
      const payload: Record<string, unknown> = { name: id, enabled: true };
      if (remote) {
        payload.transport = "streamable_http";
        payload.url = remote.url;
      } else if (pkg?.registry_type === "npm") {
        payload.transport = "stdio";
        payload.command = "npx";
        payload.args = ["-y", pkg.identifier];
      } else if (pkg?.registry_type === "pypi") {
        payload.transport = "stdio";
        payload.command = "uvx";
        payload.args = [pkg.identifier];
      } else {
        toast.show("Unsupported package type", "warning");
        return;
      }
      await api.addMCPServer(payload);
      toast.show(`${id} installed`, "success");
      onSaved();
      await refreshStatus();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Install failed", "danger");
    } finally {
      setInstalling(null);
    }
  };

  const presetsByCategory = useMemo(() => {
    const map: Record<string, MCPPreset[]> = {};
    for (const preset of presets) (map[preset.category] ??= []).push(preset);
    return map;
  }, [presets]);

  return (
    <div className="flex flex-col gap-5">
      <Panel>
        <PanelHeader
          title="MCP servers"
          description="Manual servers, installed presets, and registry servers in one place"
          action={
            <Button variant="primary" size="sm" onPress={() => setAdding(true)}>
              <Plus size={15} />
              Add manually
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
              <div className="mt-3 flex flex-wrap items-center gap-2 pl-6">
                <span className="text-xs font-medium text-muted">Export to</span>
                <Button
                  size="sm"
                  variant={srv.export_codex ? "primary" : "tertiary"}
                  isDisabled={busy === `${name}:export_codex`}
                  onPress={() => setExportFlag(name, srv, "export_codex", !srv.export_codex)}
                  aria-label={`Toggle Codex export for ${name}`}
                >
                  {srv.export_codex ? <Check size={13} /> : <Plus size={13} />}
                  Codex
                </Button>
                <Button
                  size="sm"
                  variant={srv.export_claude ? "primary" : "tertiary"}
                  isDisabled={busy === `${name}:export_claude`}
                  onPress={() => setExportFlag(name, srv, "export_claude", !srv.export_claude)}
                  aria-label={`Toggle Claude export for ${name}`}
                >
                  {srv.export_claude ? <Check size={13} /> : <Plus size={13} />}
                  Claude
                </Button>
              </div>
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
      </Panel>

      <Panel>
        <PanelHeader
          title="Install MCP servers"
          description="Choose a curated preset or search the official MCP registry"
        />

        <div className="mb-4 flex gap-1 rounded-xl border border-separator bg-background p-1">
          <button
            type="button"
            onClick={() => setInstallView("presets")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
              installView === "presets" ? "bg-accent text-accent-foreground" : "text-muted hover:text-foreground"
            }`}
          >
            <Sparkles size={15} />
            Presets
          </button>
          <button
            type="button"
            onClick={() => setInstallView("registry")}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
              installView === "registry" ? "bg-accent text-accent-foreground" : "text-muted hover:text-foreground"
            }`}
          >
            <Globe size={15} />
            Registry
          </button>
        </div>

        {installView === "presets" ? (
          <div className="flex flex-col gap-5">
            {Object.entries(presetsByCategory).map(([category, items]) => (
              <div key={category}>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                  {category}
                </h3>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {items.map((preset) => {
                    const isInstalled = installed.has(preset.id);
                    const isInstalling = installing === preset.id;
                    return (
                      <div key={preset.id} className="rounded-xl border border-separator bg-background p-3">
                        <div className="mb-2 flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-medium">{preset.name}</p>
                            <p className="line-clamp-2 text-xs text-muted">{preset.description}</p>
                          </div>
                          <Badge>{preset.transport}</Badge>
                        </div>
                        <p className="mb-3 truncate font-mono text-[11px] text-muted">
                          {preset.command} {preset.args.join(" ")}
                        </p>
                        <Button
                          size="sm"
                          variant={isInstalled ? "ghost" : "primary"}
                          isDisabled={isInstalled || isInstalling}
                          onPress={() => installPreset(preset)}
                        >
                          {isInstalling ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                          {isInstalled ? "Installed" : "Install"}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div>
            <form
              className="mb-4 flex gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                searchRegistry();
              }}
            >
              <div className="relative flex-1">
                <Search size={15} className="absolute left-3 top-1/2 z-10 -translate-y-1/2 text-muted" />
                <TextInput
                  value={registryQuery}
                  onChange={(event) => setRegistryQuery(event.target.value)}
                  placeholder="Search servers: notion, postgres, weather"
                  className="pl-9"
                />
              </div>
              <Button type="submit" variant="primary" isDisabled={registryLoading}>
                {registryLoading ? <Loader2 size={15} className="animate-spin" /> : "Search"}
              </Button>
            </form>
            <div className="flex flex-col gap-2">
              {registryResults.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted">
                  {registryLoading ? "Searching..." : "Search the registry to install community servers."}
                </p>
              ) : (
                registryResults.map((server) => {
                  const pkg = server.packages[0];
                  const remote = server.remotes[0];
                  const shortName = server.name.split("/").pop() ?? server.name;
                  return (
                    <div key={server.name} className="flex items-center gap-3 rounded-xl border border-separator bg-background p-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-surface-secondary text-muted">
                        {remote ? <Globe size={15} /> : <Package size={15} />}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium">{shortName}</span>
                          {pkg && <Badge>{pkg.registry_type}</Badge>}
                          {remote && <Badge color="accent">{remote.type}</Badge>}
                        </div>
                        <p className="truncate text-xs text-muted">{server.description}</p>
                        <p className="truncate font-mono text-[11px] text-muted">{server.name}</p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        isDisabled={installing === server.name || (!pkg && !remote)}
                        onPress={() => installRegistry(server)}
                      >
                        {installing === server.name ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                        Install
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </Panel>

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
    </div>
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
