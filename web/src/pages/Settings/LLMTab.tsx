import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Divider,
  Group,
  Loader,
  MultiSelect,
  NumberInput,
  PasswordInput,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { api } from "../../api/client";
import type { LLMConfig } from "../../types/config";

const PROVIDER_OPTIONS = [
  { value: "ollama", label: "Ollama (Local)" },
  { value: "anthropic", label: "Anthropic (Claude)" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Google Gemini" },
];

interface OllamaModelOption {
  value: string;
  label: string;
}

interface LLMFormValues {
  default_provider: string;
  fallback_order: string[];
  ollama_base_url: string;
  ollama_model: string;
  ollama_timeout: number;
  anthropic_model: string;
  anthropic_api_key: string;
  openai_model: string;
  openai_base_url: string;
  openai_api_key: string;
  gemini_model: string;
  gemini_api_key: string;
}

interface LLMTabProps {
  data: LLMConfig | null;
  onSaved: () => void;
}

export function LLMTab({ data, onSaved }: LLMTabProps) {
  const [saving, setSaving] = useState(false);
  const [ollamaModels, setOllamaModels] = useState<OllamaModelOption[]>([]);
  const [loadingModels, setLoadingModels] = useState(true);

  const form = useForm<LLMFormValues>({
    initialValues: {
      default_provider: "ollama",
      fallback_order: [],
      ollama_base_url: "http://localhost:11434",
      ollama_model: "",
      ollama_timeout: 60,
      anthropic_model: "claude-opus-4-8",
      anthropic_api_key: "",
      openai_model: "gpt-5.5",
      openai_base_url: "",
      openai_api_key: "",
      gemini_model: "gemini-3.5-flash",
      gemini_api_key: "",
    },
  });

  // Fetch available Ollama models
  useEffect(() => {
    setLoadingModels(true);
    api
      .getOllamaModels()
      .then((models) => {
        setOllamaModels(
          models.map((m) => ({
            value: m.name,
            label: `${m.name} (${m.size_gb}GB${m.parameters ? `, ${m.parameters}` : ""})`,
          })),
        );
      })
      .catch(() => setOllamaModels([]))
      .finally(() => setLoadingModels(false));
  }, []);

  useEffect(() => {
    if (data) {
      form.setValues({
        default_provider: data.default_provider,
        fallback_order: data.fallback_order ?? [],
        ollama_base_url: data.ollama_base_url,
        ollama_model: data.ollama_model,
        ollama_timeout: data.ollama_timeout,
        anthropic_model: data.anthropic_model,
        anthropic_api_key: "",
        openai_model: data.openai_model,
        openai_base_url: data.openai_base_url,
        openai_api_key: "",
        gemini_model: data.gemini_model,
        gemini_api_key: "",
      });
    }
  }, [data]);

  const handleSubmit = async (values: LLMFormValues) => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = { ...values };
      // Drop empty API-key fields so we never overwrite a stored key with "".
      for (const k of [
        "anthropic_api_key",
        "openai_api_key",
        "gemini_api_key",
      ] as const) {
        if (!values[k]) delete payload[k];
      }
      // Don't let the default provider also appear in the fallback chain.
      payload.fallback_order = values.fallback_order.filter(
        (p) => p !== values.default_provider,
      );
      await api.updateLLM(payload);
      notifications.show({
        title: "Saved",
        message: `LLM settings updated — default: ${values.default_provider}`,
        color: "green",
      });
      onSaved();
    } catch (e) {
      notifications.show({
        title: "Error",
        message: e instanceof Error ? e.message : "Failed to save settings",
        color: "red",
      });
    } finally {
      setSaving(false);
    }
  };

  const fallbackOptions = PROVIDER_OPTIONS.filter(
    (p) => p.value !== form.values.default_provider,
  );

  const configuredBadge = (configured: boolean | undefined) =>
    configured ? (
      <Badge variant="light" color="green" mb={4}>
        Key configured
      </Badge>
    ) : (
      <Badge variant="light" color="gray" mb={4}>
        No key
      </Badge>
    );

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack gap="md">
        <Select
          label="Default Provider"
          description="The provider used first for every request"
          data={PROVIDER_OPTIONS}
          allowDeselect={false}
          {...form.getInputProps("default_provider")}
        />

        <MultiSelect
          label="Fallback Order"
          description="Providers tried, in order, if the default fails"
          data={fallbackOptions}
          clearable
          {...form.getInputProps("fallback_order")}
        />

        <Divider
          my="xs"
          label={<Title order={6}>Ollama (Local)</Title>}
          labelPosition="left"
        />

        <Group align="flex-end" gap="xs">
          <Select
            label="Ollama Model"
            description="Select from locally available models"
            data={ollamaModels}
            searchable
            allowDeselect={false}
            rightSection={loadingModels ? <Loader size={14} /> : undefined}
            placeholder={
              loadingModels
                ? "Loading models..."
                : ollamaModels.length === 0
                  ? "No models found"
                  : "Select a model"
            }
            style={{ flex: 1 }}
            {...form.getInputProps("ollama_model")}
          />
          {data?.ollama_model && (
            <Badge variant="light" color="blue" mb={4}>
              Current: {data.ollama_model}
            </Badge>
          )}
        </Group>

        {ollamaModels.length === 0 && !loadingModels && (
          <Text size="xs" c="dimmed">
            No Ollama models found. Install one with: ollama pull qwen3:8b
          </Text>
        )}

        <Select
          label="Ollama Base URL"
          description="Ollama server address"
          data={[
            {
              value: "http://localhost:11434",
              label: "localhost:11434 (default)",
            },
          ]}
          searchable
          {...form.getInputProps("ollama_base_url")}
        />

        <NumberInput
          label="Timeout"
          description="Seconds to wait for an Ollama response"
          min={10}
          max={300}
          {...form.getInputProps("ollama_timeout")}
        />

        <Divider
          my="xs"
          label={
            <Group gap="xs">
              <Title order={6}>Anthropic (Claude)</Title>
              {configuredBadge(data?.anthropic_configured)}
            </Group>
          }
          labelPosition="left"
        />

        <TextInput
          label="Model"
          placeholder="claude-opus-4-8"
          {...form.getInputProps("anthropic_model")}
        />
        <PasswordInput
          label="API Key"
          description={
            data?.anthropic_configured
              ? "Key is configured. Leave blank to keep current (or set ANTHROPIC_API_KEY in .env)."
              : "Leave blank to use ANTHROPIC_API_KEY from .env"
          }
          placeholder="sk-ant-..."
          {...form.getInputProps("anthropic_api_key")}
        />

        <Divider
          my="xs"
          label={
            <Group gap="xs">
              <Title order={6}>OpenAI</Title>
              {configuredBadge(data?.openai_configured)}
            </Group>
          }
          labelPosition="left"
        />

        <TextInput
          label="Model"
          placeholder="gpt-5.5"
          {...form.getInputProps("openai_model")}
        />
        <TextInput
          label="Base URL"
          description="Leave blank for OpenAI; set to point at any OpenAI-compatible API"
          placeholder="https://api.openai.com/v1"
          {...form.getInputProps("openai_base_url")}
        />
        <PasswordInput
          label="API Key"
          description={
            data?.openai_configured
              ? "Key is configured. Leave blank to keep current (or set OPENAI_API_KEY in .env)."
              : "Leave blank to use OPENAI_API_KEY from .env"
          }
          placeholder="sk-..."
          {...form.getInputProps("openai_api_key")}
        />

        <Divider
          my="xs"
          label={
            <Group gap="xs">
              <Title order={6}>Google Gemini</Title>
              {configuredBadge(data?.gemini_configured)}
            </Group>
          }
          labelPosition="left"
        />

        <TextInput
          label="Model"
          placeholder="gemini-3.5-flash"
          {...form.getInputProps("gemini_model")}
        />
        <PasswordInput
          label="API Key"
          description={
            data?.gemini_configured
              ? "Key is configured. Leave blank to keep current (or set GEMINI_API_KEY in .env)."
              : "Leave blank to use GEMINI_API_KEY from .env — get a free key at ai.google.dev"
          }
          placeholder="Enter API key"
          {...form.getInputProps("gemini_api_key")}
        />

        <Group justify="flex-end">
          <Button type="submit" loading={saving}>
            Save
          </Button>
        </Group>
      </Stack>
    </form>
  );
}
