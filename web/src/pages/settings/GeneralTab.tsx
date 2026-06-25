import { useState } from "react";
import { Button } from "@heroui/react";
import { Copy, Check } from "lucide-react";
import { api } from "../../api/client";
import type { FullConfig } from "../../types/config";
import { Panel, PanelHeader, Field, TextInput, Select, useToast } from "../../components/ui";

export function GeneralTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [name, setName] = useState(config.general.name);
  const [lang, setLang] = useState(config.general.language_default);
  const [logLevel, setLogLevel] = useState(config.general.log_level);
  const [saving, setSaving] = useState(false);

  // External-client config exports
  const [codex, setCodex] = useState<string | null>(null);
  const [codexLoading, setCodexLoading] = useState(false);
  const [claude, setClaude] = useState<string | null>(null);
  const [claudeLoading, setClaudeLoading] = useState(false);
  const [copied, setCopied] = useState<"codex" | "claude" | null>(null);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateGeneral({ name, language_default: lang, log_level: logLevel });
      toast.show("General settings saved", "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  const loadCodex = async () => {
    setCodexLoading(true);
    try {
      const { toml, server_count, note } = await api.getCodexConfig();
      setCodex(toml);
      if (server_count === 0)
        toast.show("No MCP servers flagged for Codex (toggle in Settings → MCP)", "warning");
      else toast.show(`Config for ${server_count} server(s) — ${note}`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Failed", "danger");
    } finally {
      setCodexLoading(false);
    }
  };

  const loadClaude = async () => {
    setClaudeLoading(true);
    try {
      const { json, server_count, note } = await api.getClaudeConfig();
      setClaude(json);
      if (server_count === 0)
        toast.show("No MCP servers flagged for Claude (toggle in Settings → MCP)", "warning");
      else toast.show(`Config for ${server_count} server(s) — ${note}`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Failed", "danger");
    } finally {
      setClaudeLoading(false);
    }
  };

  const copy = (text: string, which: "codex" | "claude") => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(which);
      setTimeout(() => setCopied(null), 2000);
    });
  };

  return (
    <div className="flex flex-col gap-5">
      <Panel>
        <PanelHeader title="General" description="Assistant identity and logging" />
        <div className="flex flex-col gap-4">
          <Field label="Assistant name">
            <TextInput value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="Default language">
            <Select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="es">Spanish</option>
              <option value="en">English</option>
              <option value="auto">Auto-detect</option>
            </Select>
          </Field>
          <Field label="Log level">
            <Select value={logLevel} onChange={(e) => setLogLevel(e.target.value)}>
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </Select>
          </Field>
          <div className="flex justify-end">
            <Button variant="primary" onPress={save} isDisabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHeader
          title="Export MCP servers to external clients"
          description="Share selected MCP servers with Codex CLI or Claude. Pick which servers in Settings → MCP (per-server toggles)."
        />
        <div className="flex flex-col gap-4">
          {/* Codex */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Codex CLI (ChatGPT Pro)</p>
              <Button variant="ghost" size="sm" onPress={loadCodex} isDisabled={codexLoading}>
                {codexLoading ? "Generating…" : codex ? "Regenerate" : "Generate"}
              </Button>
            </div>
            {codex && (
              <div className="relative">
                <pre className="max-h-60 overflow-auto rounded-xl border border-separator bg-surface-secondary p-3 font-mono text-xs text-muted scroll-slim">
                  {codex}
                </pre>
                <button
                  type="button"
                  onClick={() => copy(codex, "codex")}
                  className="absolute right-2 top-2 rounded-lg p-1.5 text-muted transition-colors hover:bg-surface hover:text-foreground"
                  title="Copy"
                >
                  {copied === "codex" ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            )}
            <p className="text-[11px] text-muted">
              Paste into <span className="font-mono">~/.codex/config.toml</span>
            </p>
          </div>

          <div className="border-t border-separator" />

          {/* Claude */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Claude (Desktop / Code)</p>
              <Button variant="ghost" size="sm" onPress={loadClaude} isDisabled={claudeLoading}>
                {claudeLoading ? "Generating…" : claude ? "Regenerate" : "Generate"}
              </Button>
            </div>
            {claude && (
              <div className="relative">
                <pre className="max-h-60 overflow-auto rounded-xl border border-separator bg-surface-secondary p-3 font-mono text-xs text-muted scroll-slim">
                  {claude}
                </pre>
                <button
                  type="button"
                  onClick={() => copy(claude, "claude")}
                  className="absolute right-2 top-2 rounded-lg p-1.5 text-muted transition-colors hover:bg-surface hover:text-foreground"
                  title="Copy"
                >
                  {copied === "claude" ? <Check size={14} /> : <Copy size={14} />}
                </button>
              </div>
            )}
            <p className="text-[11px] text-muted">
              Add to <span className="font-mono">claude_desktop_config.json</span>, or use{" "}
              <span className="font-mono">claude mcp add-json</span>
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}
