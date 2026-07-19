import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { FullConfig, OllamaModel } from "../../api/types";
import { AlertIcon, RefreshIcon } from "../../components/icons";
import {
  Badge,
  Button,
  Field,
  Panel,
  PanelBody,
  PanelHeader,
  Select,
  Slider,
  TextInput,
} from "../../design/primitives";
import p from "../page.module.css";
import { saveLabel, useSection } from "./useSection";

const PROVIDERS = ["openai", "anthropic", "gemini", "deepseek", "ollama", "codex"];

const REASONING_EFFORTS = ["minimal", "low", "medium", "high"];

/**
 * A secret field the backend returns masked.
 *
 * The convention (PLAN.md 4.2) is: an empty box means "keep what is stored".
 * Only a non-empty value is sent, and only then does it replace the secret.
 */
function SecretField({
  label,
  configured,
  value,
  onChange,
}: {
  label: string;
  configured: boolean;
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <Field
      label={label}
      description={
        configured
          ? "Configured. Leave blank to keep the stored key."
          : "Not configured."
      }
    >
      {(id) => (
        <TextInput
          id={id}
          type="password"
          value={value}
          placeholder={configured ? "••••••••" : "sk-…"}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </Field>
  );
}

/**
 * Model picker that degrades to a free-text box when discovery found nothing.
 *
 * Defined at module scope, not inside `LLMTab`: a component declared during
 * render is a new type every pass, so React would unmount and remount it on
 * each keystroke and the input would lose focus.
 */
function ModelField({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: string[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <Field
      label={label}
      description={options.length > 0 ? `${options.length} discovered` : undefined}
    >
      {(id) =>
        options.length > 0 ? (
          <Select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
            {!options.includes(value) && <option value={value}>{value}</option>}
            {options.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
        ) : (
          <TextInput id={id} value={value} onChange={(e) => onChange(e.target.value)} />
        )
      }
    </Field>
  );
}

export function LLMTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const { draft, set, dirty, saving, commit } = useSection(
    config.llm,
    api.updateLLM,
    onSaved,
  );

  // API keys live outside the draft: they are write-only, so they must not be
  // part of the dirty comparison against the masked server view.
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [discovered, setDiscovered] = useState<Record<string, string[]>>({});
  const [discovering, setDiscovering] = useState(false);

  useEffect(() => {
    api
      .ollamaModels()
      .then(setOllamaModels)
      .catch(() => setOllamaModels([]));
  }, []);

  const discover = async () => {
    setDiscovering(true);
    try {
      setDiscovered(await api.llmModels());
    } catch {
      // Leave the manual text inputs as the fallback.
    } finally {
      setDiscovering(false);
    }
  };

  const save = () => {
    const patch: Record<string, unknown> = { ...draft };
    // Only send keys the user actually typed.
    for (const [field, value] of Object.entries(keys)) {
      if (value.trim()) patch[field] = value.trim();
    }
    void commit(patch).then(() => setKeys({}));
  };

  const setKey = (field: string, value: string) =>
    setKeys((prev) => ({ ...prev, [field]: value }));

  const keysDirty = Object.values(keys).some((v) => v.trim());

  const modelOptions = (provider: string) => discovered[provider] ?? [];

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="Routing"
          subtitle="Default provider and automatic failover order"
          actions={
            <div className={p.actions}>
              <Button
                size="sm"
                variant="ghost"
                loading={discovering}
                onClick={() => void discover()}
              >
                <RefreshIcon size={13} />
                Discover models
              </Button>
              <Button
                size="sm"
                variant="primary"
                loading={saving}
                disabled={(!dirty && !keysDirty) || saving}
                onClick={save}
              >
                {saveLabel(dirty || keysDirty, saving)}
              </Button>
            </div>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <Field label="Default provider">
                {(id) => (
                  <Select
                    id={id}
                    value={draft.default_provider}
                    onChange={(e) => set("default_provider", e.target.value)}
                  >
                    {PROVIDERS.map((provider) => (
                      <option key={provider} value={provider}>
                        {provider}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field
                label="Fallback order"
                description="Comma separated. Tried in order when the default fails."
              >
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.fallback_order.join(", ")}
                    onChange={(e) =>
                      set(
                        "fallback_order",
                        e.target.value
                          .split(",")
                          .map((v) => v.trim())
                          .filter(Boolean),
                      )
                    }
                  />
                )}
              </Field>
            </div>

            <Field label={`Tool budget — ${draft.max_tools} tools per turn`}>
              {(id) => (
                <Slider
                  id={id}
                  min={8}
                  max={200}
                  step={1}
                  value={draft.max_tools}
                  onChange={(v) => set("max_tools", v)}
                  format={(v) => String(v)}
                />
              )}
            </Field>

            <div className={p.notice}>
              <span className={p.noticeIcon}>
                <AlertIcon size={14} />
              </span>
              <span>
                This is a latency lever, not a capability switch. Set it too low and
                whole servers never reach the model — a budget of 8 once excluded
                Nextcloud entirely, because the always-included <code>dax-system</code>{" "}
                tools alone exceeded it. Set it too high and the prompt balloons;
                around 120 tools, responses took roughly 85 seconds. The default of 45
                is the tuned middle.
              </span>
            </div>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="OpenAI" />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <ModelField
                label="Model"
                options={modelOptions("openai")}
                value={draft.openai_model}
                onChange={(v) => set("openai_model", v)}
              />
              <Field
                label="Reasoning effort"
                description="Only sent on tool-less turns — it is incompatible with function tools on gpt-5.x."
              >
                {(id) => (
                  <Select
                    id={id}
                    value={draft.openai_reasoning_effort}
                    onChange={(e) => set("openai_reasoning_effort", e.target.value)}
                  >
                    {REASONING_EFFORTS.map((effort) => (
                      <option key={effort} value={effort}>
                        {effort}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
            <div className={p.row2}>
              <Field label="Base URL" description="Override for a compatible endpoint.">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.openai_base_url}
                    onChange={(e) => set("openai_base_url", e.target.value)}
                  />
                )}
              </Field>
              <SecretField
                label="API key"
                configured={draft.openai_configured}
                value={keys.openai_api_key ?? ""}
                onChange={(v) => setKey("openai_api_key", v)}
              />
            </div>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Anthropic" />
        <PanelBody>
          <div className={p.row2}>
            <ModelField
              label="Model"
              options={modelOptions("anthropic")}
              value={draft.anthropic_model}
              onChange={(v) => set("anthropic_model", v)}
            />
            <SecretField
              label="API key"
              configured={draft.anthropic_configured}
              value={keys.anthropic_api_key ?? ""}
              onChange={(v) => setKey("anthropic_api_key", v)}
            />
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Gemini" />
        <PanelBody>
          <div className={p.row2}>
            <ModelField
              label="Model"
              options={modelOptions("gemini")}
              value={draft.gemini_model}
              onChange={(v) => set("gemini_model", v)}
            />
            <SecretField
              label="API key"
              configured={draft.gemini_configured}
              value={keys.gemini_api_key ?? ""}
              onChange={(v) => setKey("gemini_api_key", v)}
            />
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="DeepSeek" />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <ModelField
                label="Model"
                options={modelOptions("deepseek")}
                value={draft.deepseek_model}
                onChange={(v) => set("deepseek_model", v)}
              />
              <Field label="Base URL">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.deepseek_base_url}
                    onChange={(e) => set("deepseek_base_url", e.target.value)}
                  />
                )}
              </Field>
            </div>
            <SecretField
              label="API key"
              configured={draft.deepseek_configured}
              value={keys.deepseek_api_key ?? ""}
              onChange={(v) => setKey("deepseek_api_key", v)}
            />
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Ollama"
          subtitle="Local models, served over the OpenAI-compatible API"
          actions={
            ollamaModels.length > 0 && (
              <Badge tone="success">{ollamaModels.length} installed</Badge>
            )
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <Field label="Model">
                {(id) =>
                  ollamaModels.length > 0 ? (
                    <Select
                      id={id}
                      value={draft.ollama_model}
                      onChange={(e) => set("ollama_model", e.target.value)}
                    >
                      {!ollamaModels.some((m) => m.name === draft.ollama_model) && (
                        <option value={draft.ollama_model}>{draft.ollama_model}</option>
                      )}
                      {ollamaModels.map((m) => (
                        <option key={m.name} value={m.name}>
                          {m.name} ({m.parameters}, {m.size_gb} GB)
                        </option>
                      ))}
                    </Select>
                  ) : (
                    <TextInput
                      id={id}
                      value={draft.ollama_model}
                      onChange={(e) => set("ollama_model", e.target.value)}
                    />
                  )
                }
              </Field>
              <Field label="Base URL">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.ollama_base_url}
                    onChange={(e) => set("ollama_base_url", e.target.value)}
                  />
                )}
              </Field>
            </div>
            <Field label="Timeout (seconds)">
              {(id) => (
                <TextInput
                  id={id}
                  type="number"
                  value={draft.ollama_timeout}
                  onChange={(e) => set("ollama_timeout", Number(e.target.value))}
                />
              )}
            </Field>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Codex"
          subtitle="Subprocess provider — text only, and it runs its own tool loop"
        />
        <PanelBody>
          <div className={p.row2}>
            <Field label="Binary path">
              {(id) => (
                <TextInput
                  id={id}
                  value={draft.codex_binary}
                  onChange={(e) => set("codex_binary", e.target.value)}
                />
              )}
            </Field>
            <Field label="Model">
              {(id) => (
                <TextInput
                  id={id}
                  value={draft.codex_model}
                  onChange={(e) => set("codex_model", e.target.value)}
                />
              )}
            </Field>
          </div>
        </PanelBody>
      </Panel>
    </div>
  );
}
