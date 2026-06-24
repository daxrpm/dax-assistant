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

  // Codex config
  const [codex, setCodex] = useState<string | null>(null);
  const [codexLoading, setCodexLoading] = useState(false);
  const [copied, setCopied] = useState(false);

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
      if (server_count === 0) toast.show("No enabled MCP servers found", "warning");
      else toast.show(`Config for ${server_count} server(s) — ${note}`, "success");
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Failed", "danger");
    } finally {
      setCodexLoading(false);
    }
  };

  const copyCodex = () => {
    if (!codex) return;
    navigator.clipboard.writeText(codex).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
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
          title="Codex CLI integration"
          description="Use Dax's MCP servers from OpenAI Codex CLI (works with ChatGPT Pro account)"
        />
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted">
            Generate a <span className="font-mono">~/.codex/config.toml</span> snippet that
            connects Codex CLI to all of Dax's enabled MCP servers. Works with a ChatGPT Pro
            account or a separate OpenAI API key.
          </p>
          {!codex ? (
            <Button variant="ghost" onPress={loadCodex} isDisabled={codexLoading}>
              {codexLoading ? "Generating…" : "Generate config"}
            </Button>
          ) : (
            <div className="relative">
              <pre className="overflow-x-auto rounded-xl border border-separator bg-surface-secondary p-3 font-mono text-xs text-muted scroll-slim">
                {codex}
              </pre>
              <button
                type="button"
                onClick={copyCodex}
                className="absolute right-2 top-2 rounded-lg p-1.5 text-muted transition-colors hover:bg-surface hover:text-foreground"
                title="Copy to clipboard"
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
              </button>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}
