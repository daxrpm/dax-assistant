import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { RefreshCw, Trash2, Plus, CheckCircle2, XCircle } from "lucide-react";
import { api, type MCPServerStatus } from "../../api/client";
import type { FullConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  TextArea,
  Select,
  Badge,
  Modal,
  useToast,
} from "../../components/ui";

/** Parse "KEY=value" lines into an object. */
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
                    <Badge color={connected ? "success" : "default"}>
                      {st.tool_count} tools
                    </Badge>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-1">
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
            </div>
          );
        })}
      </div>

      <AddServerModal
        open={adding}
        onClose={() => setAdding(false)}
        onAdded={async () => {
          setAdding(false);
          onSaved();
          await refreshStatus();
        }}
      />
    </Panel>
  );
}

function AddServerModal({
  open,
  onClose,
  onAdded,
}: {
  open: boolean;
  onClose: () => void;
  onAdded: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [transport, setTransport] = useState("stdio");
  const [command, setCommand] = useState("");
  const [args, setArgs] = useState("");
  const [url, setUrl] = useState("");
  const [env, setEnv] = useState("");
  const [saving, setSaving] = useState(false);

  const submit = async () => {
    if (!name.trim()) {
      toast.show("Name is required", "warning");
      return;
    }
    setSaving(true);
    try {
      await api.addMCPServer({
        name: name.trim(),
        transport,
        command: transport === "stdio" ? command.trim() : "",
        args:
          transport === "stdio"
            ? args.split(" ").map((a) => a.trim()).filter(Boolean)
            : [],
        url: transport !== "stdio" ? url.trim() : "",
        env: parseEnv(env),
        enabled: true,
      });
      toast.show(`Added ${name}`, "success");
      setName("");
      setCommand("");
      setArgs("");
      setUrl("");
      setEnv("");
      onAdded();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Add failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Add MCP server"
      footer={
        <>
          <Button variant="tertiary" onPress={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onPress={submit} isDisabled={saving}>
            {saving ? "Adding…" : "Add"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Name">
          <TextInput
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="filesystem"
          />
        </Field>
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
          <Field label="URL">
            <TextInput
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/mcp"
            />
          </Field>
        )}
        <Field
          label="Environment variables"
          description="One KEY=value per line. Use {env:NAME} to read a secret from .env."
        >
          <TextArea
            rows={3}
            value={env}
            onChange={(e) => setEnv(e.target.value)}
            placeholder={"NEXTCLOUD_HOST=https://cloud.example.com\nNEXTCLOUD_USERNAME=me\nNEXTCLOUD_PASSWORD={env:NEXTCLOUD_PASSWORD}"}
          />
        </Field>
      </div>
    </Modal>
  );
}
