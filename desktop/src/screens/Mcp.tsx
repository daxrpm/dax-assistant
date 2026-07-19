import { useState } from "react";
import { api } from "../api/client";
import { CheckIcon, CopyIcon, McpIcon } from "../components/icons";
import { McpServers } from "../components/McpServers";
import {
  Button,
  Panel,
  PanelBody,
  PanelHeader,
  Spinner,
  useToast,
} from "../design/primitives";
import { useConfig } from "../hooks/useConfig";
import p from "./page.module.css";

/** Copy the generated Codex TOML / Claude JSON for the flagged servers. */
function ExportPanel() {
  const toast = useToast();
  const [copied, setCopied] = useState<"codex" | "claude" | null>(null);

  const copy = async (which: "codex" | "claude") => {
    try {
      const data =
        which === "codex" ? await api.codexConfig() : await api.claudeConfig();
      const text = "toml" in data ? data.toml : data.json;
      if (data.server_count === 0) {
        toast.show(
          `No servers flagged for ${which === "codex" ? "Codex" : "Claude"} export yet`,
          "neutral",
        );
        return;
      }
      await navigator.clipboard.writeText(text);
      setCopied(which);
      setTimeout(() => setCopied(null), 1500);
      toast.show(`${data.server_count} server(s) copied`, "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Export failed", "danger");
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Export to other AI clients"
        subtitle="Generates config for the servers you flagged per row above"
      />
      <PanelBody>
        <div className={p.actions}>
          <Button size="sm" variant="secondary" onClick={() => void copy("codex")}>
            {copied === "codex" ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
            Copy Codex config
          </Button>
          <Button size="sm" variant="secondary" onClick={() => void copy("claude")}>
            {copied === "claude" ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
            Copy Claude config
          </Button>
        </div>
      </PanelBody>
    </Panel>
  );
}

export function Mcp() {
  const { config, loading, refresh } = useConfig();

  return (
    <div className={p.page}>
      <div className={p.pageHead}>
        <div className={p.pageMark}>
          <McpIcon size={19} />
        </div>
        <div>
          <h1 className={p.pageTitle}>MCP Servers</h1>
          <p className={p.pageSubtitle}>
            Manage tool servers, authenticate remotes, and export per server
          </p>
        </div>
      </div>

      {loading || !config ? (
        <Spinner size={18} />
      ) : (
        <>
          <McpServers config={config} onSaved={refresh} />
          <ExportPanel />
        </>
      )}
    </div>
  );
}
