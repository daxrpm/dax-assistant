import { useState } from "react";
import { Button } from "@heroui/react";
import { Server, Download, Copy, Check } from "lucide-react";
import { useConfig } from "../hooks/useConfig";
import { api } from "../api/client";
import { McpTab } from "./settings/McpTab";
import { Panel, PanelHeader, useToast } from "../components/ui";

/* ── Export-to-external-client panel ──────────────────────────────────────── */

function ExportPanel() {
  const toast = useToast();
  const [copied, setCopied] = useState<"codex" | "claude" | null>(null);

  const copy = async (which: "codex" | "claude") => {
    try {
      let text: string;
      let count: number;
      if (which === "codex") {
        const data = await api.getCodexConfig();
        text = data.toml;
        count = data.server_count;
      } else {
        const data = await api.getClaudeConfig();
        text = data.json;
        count = data.server_count;
      }
      if (count === 0) {
        toast.show(
          `No servers flagged for ${which === "codex" ? "Codex" : "Claude"} export yet`,
          "warning",
        );
        return;
      }
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(null), 1500);
      toast.show(`${count} server(s) copied to clipboard`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Export failed", "danger");
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Export to other AI clients"
        description="Generate config for the servers you flagged per row above"
      />
      <div className="flex flex-wrap gap-2">
        <Button variant="tertiary" size="sm" onPress={() => copy("codex")}>
          {copied === "codex" ? <Check size={14} /> : <Copy size={14} />}
          Copy Codex config
        </Button>
        <Button variant="tertiary" size="sm" onPress={() => copy("claude")}>
          {copied === "claude" ? <Check size={14} /> : <Copy size={14} />}
          Copy Claude config
        </Button>
      </div>
    </Panel>
  );
}

/* ── Standalone MCP page (no longer a Settings tab) ───────────────────────── */

export function McpPage() {
  const { config, loading, refresh } = useConfig();

  return (
    <div className="h-full overflow-y-auto scroll-slim p-6">
      <div className="mx-auto flex max-w-5xl flex-col gap-5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-accent text-accent-foreground">
            <Server size={20} />
          </div>
          <div>
            <h1 className="text-xl font-semibold">MCP Servers</h1>
            <p className="text-sm text-muted">
              Manage tool servers, install from presets or the registry, and export per server
            </p>
          </div>
        </div>

        {loading || !config ? (
          <p className="flex items-center gap-2 text-sm text-muted">
            <Download size={14} className="animate-pulse" />
            Loading MCP servers…
          </p>
        ) : (
          <>
            <McpTab config={config} onSaved={refresh} />
            <ExportPanel />
          </>
        )}
      </div>
    </div>
  );
}
