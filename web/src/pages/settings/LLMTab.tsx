import { useEffect, useState } from "react";
import { Button } from "@heroui/react";
import { api } from "../../api/client";
import type { FullConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  Select,
  Badge,
  useToast,
} from "../../components/ui";

const PROVIDERS = [
  { id: "ollama", label: "Ollama (Local)" },
  { id: "anthropic", label: "Anthropic (Claude)" },
  { id: "openai", label: "OpenAI" },
  { id: "gemini", label: "Google Gemini" },
  { id: "codex", label: "Codex (ChatGPT Pro)" },
];

export function LLMTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const llm = config.llm;
  const [provider, setProvider] = useState(llm.default_provider);
  const [fallback, setFallback] = useState<string[]>(llm.fallback_order ?? []);
  const [maxTools, setMaxTools] = useState(llm.max_tools ?? 45);
  const [ollamaModel, setOllamaModel] = useState(llm.ollama_model);
  const [ollamaUrl, setOllamaUrl] = useState(llm.ollama_base_url);
  const [ollamaTimeout, setOllamaTimeout] = useState(llm.ollama_timeout);
  const [anthropicModel, setAnthropicModel] = useState(llm.anthropic_model);
  const [anthropicKey, setAnthropicKey] = useState("");
  const [openaiModel, setOpenaiModel] = useState(llm.openai_model);
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState(llm.openai_base_url);
  const [openaiKey, setOpenaiKey] = useState("");
  const [openaiReasoning, setOpenaiReasoning] = useState(llm.openai_reasoning_effort ?? "low");
  const [geminiModel, setGeminiModel] = useState(llm.gemini_model);
  const [geminiKey, setGeminiKey] = useState("");
  const [codexBinary, setCodexBinary] = useState(llm.codex_binary ?? "codex");
  const [codexModel, setCodexModel] = useState(llm.codex_model ?? "");
  const [models, setModels] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .getOllamaModels()
      .then((m) => setModels(m.map((x) => x.name)))
      .catch(() => setModels([]));
  }, []);

  const toggleFallback = (id: string) =>
    setFallback((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id],
    );

  const save = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        default_provider: provider,
        fallback_order: fallback.filter((p) => p !== provider),
        max_tools: maxTools,
        ollama_model: ollamaModel,
        ollama_base_url: ollamaUrl,
        ollama_timeout: ollamaTimeout,
        anthropic_model: anthropicModel,
        openai_model: openaiModel,
        openai_base_url: openaiBaseUrl,
        openai_reasoning_effort: openaiReasoning,
        gemini_model: geminiModel,
        codex_binary: codexBinary,
        codex_model: codexModel,
      };
      if (anthropicKey) payload.anthropic_api_key = anthropicKey;
      if (openaiKey) payload.openai_api_key = openaiKey;
      if (geminiKey) payload.gemini_api_key = geminiKey;
      await api.updateLLM(payload);
      toast.show(`LLM updated — default: ${provider}`, "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-5">
      <Panel>
        <PanelHeader
          title="Routing"
          description="Default provider plus the fallback chain (tried in order)"
        />
        <div className="flex flex-col gap-4">
          <Field label="Default provider">
            <Select value={provider} onChange={(e) => setProvider(e.target.value)}>
              {PROVIDERS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field
            label="Fallback order"
            description="Used, in order, if the default fails"
          >
            <div className="flex flex-wrap gap-2">
              {PROVIDERS.filter((p) => p.id !== provider).map((p) => {
                const on = fallback.includes(p.id);
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => toggleFallback(p.id)}
                    className={
                      "rounded-full px-3 py-1 text-xs font-medium transition-colors " +
                      (on
                        ? "bg-accent text-accent-foreground"
                        : "bg-surface-secondary text-muted hover:text-foreground")
                    }
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </Field>
          <Field
            label="Max tools per request"
            description="Lower = faster responses. Tools are picked by relevance to your query (recommended 30–50; raising this slows the model)."
          >
            <TextInput
              type="number"
              value={maxTools}
              onChange={(e) => setMaxTools(Number(e.target.value))}
            />
          </Field>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Ollama (Local)" />
        <div className="flex flex-col gap-4">
          <Field
            label="Model"
            description={
              models.length === 0 ? "No local models found (ollama pull …)" : undefined
            }
          >
            {models.length > 0 ? (
              <Select value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)}>
                {!models.includes(ollamaModel) && ollamaModel && (
                  <option value={ollamaModel}>{ollamaModel}</option>
                )}
                {models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </Select>
            ) : (
              <TextInput
                value={ollamaModel}
                onChange={(e) => setOllamaModel(e.target.value)}
                placeholder="llama3.1:8b"
              />
            )}
          </Field>
          <Field label="Base URL">
            <TextInput value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} />
          </Field>
          <Field label="Timeout (seconds)">
            <TextInput
              type="number"
              value={ollamaTimeout}
              onChange={(e) => setOllamaTimeout(Number(e.target.value))}
            />
          </Field>
        </div>
      </Panel>

      <ProviderPanel
        title="Anthropic (Claude)"
        configured={llm.anthropic_configured}
        model={anthropicModel}
        onModel={setAnthropicModel}
        modelPlaceholder="claude-opus-4-8"
        apiKey={anthropicKey}
        onApiKey={setAnthropicKey}
        keyEnvVar="ANTHROPIC_API_KEY"
      />

      <ProviderPanel
        title="OpenAI"
        configured={llm.openai_configured}
        model={openaiModel}
        onModel={setOpenaiModel}
        modelPlaceholder="gpt-5.5"
        apiKey={openaiKey}
        onApiKey={setOpenaiKey}
        keyEnvVar="OPENAI_API_KEY"
        baseUrl={openaiBaseUrl}
        onBaseUrl={setOpenaiBaseUrl}
        reasoning={openaiReasoning}
        onReasoning={setOpenaiReasoning}
      />

      <ProviderPanel
        title="Google Gemini"
        configured={llm.gemini_configured}
        model={geminiModel}
        onModel={setGeminiModel}
        modelPlaceholder="gemini-3.5-flash"
        apiKey={geminiKey}
        onApiKey={setGeminiKey}
        keyEnvVar="GEMINI_API_KEY"
      />

      <Panel>
        <PanelHeader
          title="Codex (ChatGPT Pro)"
          description="Runs `codex exec` as a subprocess using your ChatGPT plan. Returns text only — Codex runs its own tools. Run `codex login` first."
        />
        <div className="flex flex-col gap-4">
          <Field label="Binary" description="Path to the codex CLI, or just 'codex' if on PATH">
            <TextInput
              value={codexBinary}
              onChange={(e) => setCodexBinary(e.target.value)}
              placeholder="codex"
            />
          </Field>
          <Field label="Model" description="Leave blank for your account default">
            <TextInput
              value={codexModel}
              onChange={(e) => setCodexModel(e.target.value)}
              placeholder="gpt-5.5-codex"
            />
          </Field>
        </div>
      </Panel>

      <div className="flex justify-end">
        <Button variant="primary" onPress={save} isDisabled={saving}>
          {saving ? "Saving…" : "Save"}
        </Button>
      </div>
    </div>
  );
}

function ProviderPanel({
  title,
  configured,
  model,
  onModel,
  modelPlaceholder,
  apiKey,
  onApiKey,
  keyEnvVar,
  baseUrl,
  onBaseUrl,
  reasoning,
  onReasoning,
}: {
  title: string;
  configured: boolean;
  model: string;
  onModel: (v: string) => void;
  modelPlaceholder: string;
  apiKey: string;
  onApiKey: (v: string) => void;
  keyEnvVar: string;
  baseUrl?: string;
  onBaseUrl?: (v: string) => void;
  reasoning?: string;
  onReasoning?: (v: string) => void;
}) {
  return (
    <Panel>
      <PanelHeader
        title={title}
        action={
          <Badge color={configured ? "success" : "default"}>
            {configured ? "Key configured" : "No key"}
          </Badge>
        }
      />
      <div className="flex flex-col gap-4">
        <Field label="Model">
          <TextInput
            value={model}
            onChange={(e) => onModel(e.target.value)}
            placeholder={modelPlaceholder}
          />
        </Field>
        {onBaseUrl && (
          <Field
            label="Base URL"
            description="Leave blank for the default; set to use any OpenAI-compatible API"
          >
            <TextInput
              value={baseUrl ?? ""}
              onChange={(e) => onBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
            />
          </Field>
        )}
        {onReasoning && (
          <Field
            label="Reasoning effort"
            description="Lower = faster. Only applied to tool-less turns (gpt-5.x rejects it with function tools)."
          >
            <Select value={reasoning ?? "low"} onChange={(e) => onReasoning(e.target.value)}>
              <option value="minimal">Minimal (fastest)</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </Select>
          </Field>
        )}
        <Field
          label="API key"
          description={`Leave blank to keep current or use ${keyEnvVar} from .env`}
        >
          <TextInput
            type="password"
            value={apiKey}
            onChange={(e) => onApiKey(e.target.value)}
            placeholder="••••••••"
          />
        </Field>
      </div>
    </Panel>
  );
}
