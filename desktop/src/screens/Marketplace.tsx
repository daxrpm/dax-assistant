import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api } from "../api/client";
import type { MCPPreset, RegistryServer } from "../api/types";
import { PlusIcon, SearchIcon, StoreIcon } from "../components/icons";
import { McpServers, emptyDraft, type ServerDraft } from "../components/McpServers";
import {
  Badge,
  Button,
  EmptyState,
  Panel,
  PanelBody,
  PanelHeader,
  SegmentedControl,
  Spinner,
  TextInput,
  useToast,
} from "../design/primitives";
import { useConfig } from "../hooks/useConfig";
import p from "./page.module.css";
import s from "./Marketplace.module.css";

function presetToDraft(preset: MCPPreset): ServerDraft {
  return {
    ...emptyDraft(),
    name: preset.id || preset.name,
    transport: preset.transport || "stdio",
    command: preset.command ?? "",
    args: (preset.args ?? []).join(" "),
    env: Object.entries(preset.env ?? {})
      .map(([k, v]) => `${k}=${v}`)
      .join("\n"),
  };
}

function registryToDraft(server: RegistryServer): ServerDraft {
  const remote = server.remotes?.[0];
  const pkg = server.packages?.[0];
  // Prefer a remote endpoint when the entry advertises one; otherwise assume an
  // npm/pypi package launched through its usual runner.
  if (remote) {
    return {
      ...emptyDraft(),
      name: server.name.split("/").pop() ?? server.name,
      transport: "http",
      url: remote.url,
    };
  }
  const runner = pkg?.registry_type === "pypi" ? "uvx" : "npx";
  return {
    ...emptyDraft(),
    name: server.name.split("/").pop() ?? server.name,
    transport: "stdio",
    command: runner,
    args: pkg?.identifier ?? "",
  };
}

export function Marketplace() {
  const toast = useToast();
  const { config, refresh } = useConfig();
  const [mode, setMode] = useState<"presets" | "registry">("presets");
  const [presets, setPresets] = useState<MCPPreset[]>([]);
  const [loadingPresets, setLoadingPresets] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RegistryServer[]>([]);
  const [searching, setSearching] = useState(false);
  const [registryError, setRegistryError] = useState<string | null>(null);
  const [prefill, setPrefill] = useState<ServerDraft | null>(null);

  useEffect(() => {
    api
      .mcpPresets()
      .then(setPresets)
      .catch(() => setPresets([]))
      .finally(() => setLoadingPresets(false));
  }, []);

  const grouped = useMemo(() => {
    const byCategory = new Map<string, MCPPreset[]>();
    for (const preset of presets) {
      const key = preset.category || "Other";
      byCategory.set(key, [...(byCategory.get(key) ?? []), preset]);
    }
    return [...byCategory.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [presets]);

  const search = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setRegistryError(null);
    try {
      const data = await api.searchMcpRegistry(query.trim());
      // The backend reports upstream registry failures in-band rather than
      // as an HTTP error.
      if (data.error) {
        setRegistryError(data.error);
        setResults([]);
      } else {
        setResults(data.servers ?? []);
      }
    } catch (err) {
      setRegistryError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setSearching(false);
    }
  };

  const install = (draft: ServerDraft) => {
    setPrefill(draft);
    toast.show(`Review ${draft.name} and save to install`, "neutral");
  };

  return (
    <div className={p.page}>
      <div className={p.pageHead}>
        <div className={p.pageMark}>
          <StoreIcon size={19} />
        </div>
        <div>
          <h1 className={p.pageTitle}>Marketplace</h1>
          <p className={p.pageSubtitle}>
            Install a curated preset or search the public MCP registry
          </p>
        </div>
      </div>

      <SegmentedControl
        value={mode}
        onChange={setMode}
        items={[
          { id: "presets", label: "Curated presets" },
          { id: "registry", label: "Registry search" },
        ]}
      />

      {mode === "presets" ? (
        loadingPresets ? (
          <Spinner size={18} />
        ) : grouped.length === 0 ? (
          <EmptyState
            icon={<StoreIcon size={20} />}
            title="No presets available"
            body="The backend returned an empty preset list."
          />
        ) : (
          grouped.map(([category, items]) => (
            <Panel key={category}>
              <PanelHeader title={category} subtitle={`${items.length} available`} />
              <PanelBody>
                <div className={s.cards}>
                  {items.map((preset) => {
                    const installed = Boolean(config?.mcp.servers[preset.id]);
                    const requiredEnv = Object.keys(preset.env ?? {});
                    return (
                      <div key={preset.id} className={s.card}>
                        <div className={s.cardHead}>
                          <span className={s.cardName}>{preset.name}</span>
                          {installed && <Badge tone="success">Installed</Badge>}
                        </div>
                        <p className={s.cardBody}>{preset.description}</p>
                        {requiredEnv.length > 0 && (
                          <div className={s.cardEnv}>
                            Needs: {requiredEnv.join(", ")}
                          </div>
                        )}
                        <Button
                          size="sm"
                          variant={installed ? "ghost" : "secondary"}
                          onClick={() => install(presetToDraft(preset))}
                        >
                          <PlusIcon size={12} />
                          {installed ? "Reconfigure" : "Install"}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </PanelBody>
            </Panel>
          ))
        )
      ) : (
        <Panel>
          <PanelHeader title="Registry search" subtitle="Public MCP server registry" />
          <PanelBody>
            <form className={p.actions} onSubmit={search}>
              <TextInput
                className={p.grow}
                value={query}
                placeholder="Search for a server…"
                onChange={(e) => setQuery(e.target.value)}
              />
              <Button type="submit" variant="secondary" loading={searching}>
                <SearchIcon size={13} />
                Search
              </Button>
            </form>

            {registryError && <p className={s.error}>{registryError}</p>}

            {!registryError && results.length > 0 && (
              <div className={s.cards}>
                {results.map((server) => (
                  <div key={server.name} className={s.card}>
                    <div className={s.cardHead}>
                      <span className={s.cardName}>{server.name}</span>
                      <span className={p.dim}>{server.version}</span>
                    </div>
                    <p className={s.cardBody}>{server.description}</p>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => install(registryToDraft(server))}
                    >
                      <PlusIcon size={12} />
                      Install
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </PanelBody>
        </Panel>
      )}

      {config && (
        <McpServers
          config={config}
          onSaved={refresh}
          prefill={prefill}
          onPrefillConsumed={() => setPrefill(null)}
        />
      )}
    </div>
  );
}
