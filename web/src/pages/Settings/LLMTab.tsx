import { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Group,
  Loader,
  NumberInput,
  PasswordInput,
  Select,
  Stack,
  Text,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { api } from "../../api/client";
import type { LLMConfig } from "../../types/config";

const LLM_PROVIDER = {
  OLLAMA: "ollama",
  GEMINI: "gemini",
} as const;

type LLMProvider = (typeof LLM_PROVIDER)[keyof typeof LLM_PROVIDER];

const PROVIDER_OPTIONS = [
  { value: LLM_PROVIDER.OLLAMA, label: "Ollama (Local)" },
  { value: LLM_PROVIDER.GEMINI, label: "Gemini (Cloud Fallback)" },
];

interface OllamaModelOption {
  value: string;
  label: string;
}

interface LLMFormValues {
  default_provider: LLMProvider;
  ollama_base_url: string;
  ollama_model: string;
  ollama_timeout: number;
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
      default_provider: LLM_PROVIDER.OLLAMA,
      ollama_base_url: "http://localhost:11434",
      ollama_model: "",
      ollama_timeout: 60,
      gemini_model: "",
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
        default_provider: data.default_provider as LLMProvider,
        ollama_base_url: data.ollama_base_url,
        ollama_model: data.ollama_model,
        ollama_timeout: data.ollama_timeout,
        gemini_model: data.gemini_model,
        gemini_api_key: "",
      });
    }
  }, [data]);

  const handleSubmit = async (values: LLMFormValues) => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = { ...values };
      if (!values.gemini_api_key) {
        delete payload.gemini_api_key;
      }
      await api.updateLLM(payload);
      notifications.show({
        title: "Saved",
        message: `LLM settings updated — model: ${values.ollama_model}`,
        color: "green",
      });
      onSaved();
    } catch (e) {
      notifications.show({
        title: "Error",
        message:
          e instanceof Error ? e.message : "Failed to save settings",
        color: "red",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack gap="md">
        <Select
          label="Default Provider"
          data={PROVIDER_OPTIONS}
          {...form.getInputProps("default_provider")}
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
          description="Seconds to wait for LLM response"
          min={10}
          max={300}
          {...form.getInputProps("ollama_timeout")}
        />

        <Select
          label="Gemini Model"
          description="Cloud fallback — used when Ollama fails"
          data={[
            {
              value: "gemini/gemini-2.5-flash-lite",
              label: "Gemini 2.5 Flash Lite (free tier)",
            },
            {
              value: "gemini/gemini-2.5-flash",
              label: "Gemini 2.5 Flash",
            },
          ]}
          searchable
          {...form.getInputProps("gemini_model")}
        />

        <PasswordInput
          label="Gemini API Key"
          description={
            data?.gemini_configured
              ? "Key is configured. Leave blank to keep current."
              : "Optional — get free key at ai.google.dev"
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
