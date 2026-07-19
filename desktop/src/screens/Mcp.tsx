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
import { useI18n } from "../i18n/I18n";

/** Copy the generated Codex TOML / Claude JSON for the flagged servers. */
function ExportPanel() {
  const { text } = useI18n();
  const toast = useToast();
  const [copied, setCopied] = useState<"codex" | "claude" | null>(null);

  const copy = async (which: "codex" | "claude") => {
    try {
      const data =
        which === "codex" ? await api.codexConfig() : await api.claudeConfig();
      const configText = "toml" in data ? data.toml : data.json;
      if (data.server_count === 0) {
        toast.show(
          text(`Aún no hay servidores marcados para exportar a ${which === "codex" ? "Codex" : "Claude"}`, `No servers flagged for ${which === "codex" ? "Codex" : "Claude"} export yet`),
          "neutral",
        );
        return;
      }
      await navigator.clipboard.writeText(configText);
      setCopied(which);
      setTimeout(() => setCopied(null), 1500);
      toast.show(text(`${data.server_count} servidor(es) copiado(s)`, `${data.server_count} server(s) copied`), "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : text("Error al exportar", "Export failed"), "danger");
    }
  };

  return (
    <Panel>
      <PanelHeader
        title={text("Exportar a otros clientes de IA", "Export to other AI clients")}
        subtitle={text("Genera configuración para los servidores marcados arriba", "Generates config for the servers you flagged per row above")}
      />
      <PanelBody>
        <div className={p.actions}>
          <Button size="sm" variant="secondary" onClick={() => void copy("codex")}>
            {copied === "codex" ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
            {text("Copiar configuración de Codex", "Copy Codex config")}
          </Button>
          <Button size="sm" variant="secondary" onClick={() => void copy("claude")}>
            {copied === "claude" ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
            {text("Copiar configuración de Claude", "Copy Claude config")}
          </Button>
        </div>
      </PanelBody>
    </Panel>
  );
}

export function Mcp() {
  const { text } = useI18n();
  const { config, loading, refresh } = useConfig();

  return (
    <div className={p.page}>
      <div className={p.pageHead}>
        <div className={p.pageMark}>
          <McpIcon size={19} />
        </div>
        <div>
          <h1 className={p.pageTitle}>{text("Servidores MCP", "MCP Servers")}</h1>
          <p className={p.pageSubtitle}>
            {text("Gestiona servidores de herramientas, autentica remotos y exporta cada servidor", "Manage tool servers, authenticate remotes, and export per server")}
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
