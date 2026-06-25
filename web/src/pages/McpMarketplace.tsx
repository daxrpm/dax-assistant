import { useEffect, useMemo, useState } from "react";
import { Button } from "@heroui/react";
import {
  Search,
  Download,
  Package,
  Globe,
  Loader2,
  Sparkles,
  Server,
  Check,
} from "lucide-react";
import { api, type MCPPreset, type RegistryServer } from "../api/client";
import { Panel, PanelHeader, Badge, TextInput, useToast } from "../components/ui";
import { cn } from "../lib/cn";

/* ── Preset card ──────────────────────────────────────────────────────────── */

function PresetCard({
  preset,
  installed,
  onInstall,
  installing,
}: {
  preset: MCPPreset;
  installed: boolean;
  onInstall: (p: MCPPreset) => void;
  installing: boolean;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-separator bg-surface p-4 transition-colors hover:border-accent/40">
      <div className="flex items-start justify-between gap-2">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-soft text-accent">
          <Sparkles size={16} />
        </div>
        <Badge color="default">{preset.category}</Badge>
      </div>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold">{preset.name}</h3>
        <p className="mt-0.5 text-xs text-muted line-clamp-2">{preset.description}</p>
      </div>
      <code className="truncate rounded-lg bg-surface-secondary px-2 py-1 font-mono text-[10px] text-muted">
        {preset.command} {preset.args.join(" ")}
      </code>
      <Button
        size="sm"
        variant={installed ? "ghost" : "primary"}
        className="mt-1"
        isDisabled={installed || installing}
        onPress={() => onInstall(preset)}
      >
        {installed ? (
          <><Check size={14} /> Installed</>
        ) : installing ? (
          <><Loader2 size={14} className="animate-spin" /> Installing…</>
        ) : (
          <><Download size={14} /> Install</>
        )}
      </Button>
    </div>
  );
}

/* ── Registry result row ──────────────────────────────────────────────────── */

function RegistryRow({
  server,
  onInstall,
  installing,
}: {
  server: RegistryServer;
  onInstall: (s: RegistryServer) => void;
  installing: boolean;
}) {
  const pkg = server.packages[0];
  const remote = server.remotes[0];
  const shortName = server.name.split("/").pop() ?? server.name;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-separator bg-surface px-4 py-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-secondary text-muted">
        {remote ? <Globe size={14} /> : <Package size={14} />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{shortName}</span>
          {pkg && <Badge color="default">{pkg.registry_type}</Badge>}
          {remote && <Badge color="accent">{remote.type}</Badge>}
        </div>
        <p className="truncate text-xs text-muted">{server.description}</p>
        <p className="truncate font-mono text-[10px] text-muted/70">{server.name}</p>
      </div>
      <Button
        size="sm"
        variant="ghost"
        isDisabled={installing || (!pkg && !remote)}
        onPress={() => onInstall(server)}
      >
        {installing ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
        Install
      </Button>
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */

export function McpMarketplacePage() {
  const toast = useToast();
  const [presets, setPresets] = useState<MCPPreset[]>([]);
  const [installed, setInstalled] = useState<Set<string>>(new Set());
  const [installingId, setInstallingId] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RegistryServer[]>([]);
  const [searching, setSearching] = useState(false);
  const [tab, setTab] = useState<"presets" | "registry">("presets");

  const loadInstalled = () => {
    api.getMCPServers()
      .then((servers) => setInstalled(new Set(Object.keys(servers))))
      .catch(() => undefined);
  };

  useEffect(() => {
    api.getMCPPresets().then(setPresets).catch(() => setPresets([]));
    loadInstalled();
  }, []);

  const search = async () => {
    setSearching(true);
    try {
      const { servers, error } = await api.searchMCPRegistry(query, 40);
      if (error) toast.show(`Registry: ${error}`, "warning");
      setResults(servers);
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Search failed", "danger");
    } finally {
      setSearching(false);
    }
  };

  const installPreset = async (p: MCPPreset) => {
    setInstallingId(p.id);
    try {
      await api.addMCPServer({
        name: p.id,
        command: p.command,
        args: p.args,
        env: p.env,
        transport: p.transport,
        enabled: true,
      });
      setInstalled((prev) => new Set(prev).add(p.id));
      toast.show(`${p.name} installed — set any required keys in Settings → MCP`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Install failed", "danger");
    } finally {
      setInstallingId(null);
    }
  };

  const installRegistry = async (s: RegistryServer) => {
    const id = (s.name.split("/").pop() ?? s.name).replace(/[^a-zA-Z0-9_-]/g, "-");
    setInstallingId(s.name);
    try {
      const pkg = s.packages[0];
      const remote = s.remotes[0];
      const payload: Record<string, unknown> = { name: id, enabled: true };
      if (remote) {
        payload.transport = "http";
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
        toast.show("Unsupported package type — add it manually in Settings", "warning");
        return;
      }
      await api.addMCPServer(payload);
      setInstalled((prev) => new Set(prev).add(id));
      toast.show(`${id} installed`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Install failed", "danger");
    } finally {
      setInstallingId(null);
    }
  };

  const byCategory = useMemo(() => {
    const map: Record<string, MCPPreset[]> = {};
    for (const p of presets) (map[p.category] ??= []).push(p);
    return map;
  }, [presets]);

  return (
    <div className="h-full overflow-y-auto scroll-slim p-6">
      <div className="mx-auto flex max-w-4xl flex-col gap-5">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Server size={20} />
          </div>
          <div>
            <h1 className="text-xl font-semibold">MCP Marketplace</h1>
            <p className="text-sm text-muted">
              Install ready-to-use tools from curated presets or the official registry
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 rounded-xl border border-separator bg-surface p-1">
          <button
            type="button"
            onClick={() => setTab("presets")}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              tab === "presets"
                ? "bg-accent text-accent-foreground"
                : "text-muted hover:text-foreground",
            )}
          >
            <Sparkles size={14} /> Curated presets
          </button>
          <button
            type="button"
            onClick={() => setTab("registry")}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
              tab === "registry"
                ? "bg-accent text-accent-foreground"
                : "text-muted hover:text-foreground",
            )}
          >
            <Globe size={14} /> Official registry
          </button>
        </div>

        {tab === "presets" ? (
          <div className="flex flex-col gap-5">
            {Object.entries(byCategory).map(([cat, items]) => (
              <div key={cat}>
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                  {cat}
                </h2>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {items.map((p) => (
                    <PresetCard
                      key={p.id}
                      preset={p}
                      installed={installed.has(p.id)}
                      installing={installingId === p.id}
                      onInstall={installPreset}
                    />
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <Panel>
            <PanelHeader
              title="Search the official MCP registry"
              description="9,600+ community servers from registry.modelcontextprotocol.io"
            />
            <form
              onSubmit={(e) => { e.preventDefault(); search(); }}
              className="mb-4 flex gap-2"
            >
              <div className="relative flex-1">
                <Search
                  size={15}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted"
                />
                <TextInput
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search servers — e.g. notion, postgres, weather…"
                  className="pl-9"
                />
              </div>
              <Button type="submit" variant="primary" isDisabled={searching}>
                {searching ? <Loader2 size={15} className="animate-spin" /> : "Search"}
              </Button>
            </form>

            {results.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted">
                {searching ? "Searching…" : "Search to browse the registry"}
              </p>
            ) : (
              <div className="flex flex-col gap-2">
                {results.map((s) => (
                  <RegistryRow
                    key={s.name}
                    server={s}
                    installing={installingId === s.name}
                    onInstall={installRegistry}
                  />
                ))}
              </div>
            )}
          </Panel>
        )}
      </div>
    </div>
  );
}
