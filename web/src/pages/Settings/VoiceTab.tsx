import { useState, useEffect } from "react";
import {
  Button,
  Group,
  NumberInput,
  Select,
  Slider,
  Stack,
  Switch,
  Text,
  TextInput,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { notifications } from "@mantine/notifications";
import { api } from "../../api/client";
import type { VoiceConfig } from "../../types/config";

const STT_MODEL = {
  TINY: "tiny",
  BASE: "base",
  SMALL: "small",
  MEDIUM: "medium",
} as const;

type STTModel = (typeof STT_MODEL)[keyof typeof STT_MODEL];

const STT_COMPUTE_TYPE = {
  INT8: "int8",
  FLOAT16: "float16",
  FLOAT32: "float32",
} as const;

type STTComputeType = (typeof STT_COMPUTE_TYPE)[keyof typeof STT_COMPUTE_TYPE];

const STT_LANGUAGE = {
  AUTO: "auto",
  ES: "es",
  EN: "en",
} as const;

type STTLanguage = (typeof STT_LANGUAGE)[keyof typeof STT_LANGUAGE];

const STT_MODEL_OPTIONS = [
  { value: STT_MODEL.TINY, label: "Tiny" },
  { value: STT_MODEL.BASE, label: "Base" },
  { value: STT_MODEL.SMALL, label: "Small" },
  { value: STT_MODEL.MEDIUM, label: "Medium" },
];

const STT_COMPUTE_OPTIONS = [
  { value: STT_COMPUTE_TYPE.INT8, label: "int8" },
  { value: STT_COMPUTE_TYPE.FLOAT16, label: "float16" },
  { value: STT_COMPUTE_TYPE.FLOAT32, label: "float32" },
];

const STT_LANGUAGE_OPTIONS = [
  { value: STT_LANGUAGE.AUTO, label: "Auto-detect" },
  { value: STT_LANGUAGE.ES, label: "Spanish" },
  { value: STT_LANGUAGE.EN, label: "English" },
];

interface VoiceFormValues {
  enabled: boolean;
  wake_word_threshold: number;
  stt_model: STTModel;
  stt_compute_type: STTComputeType;
  stt_language: STTLanguage;
  tts_voice_es: string;
  tts_voice_en: string;
  vad_threshold: number;
  silence_duration_ms: number;
}

interface VoiceTabProps {
  data: VoiceConfig | null;
  onSaved: () => void;
}

export function VoiceTab({ data, onSaved }: VoiceTabProps) {
  const [saving, setSaving] = useState(false);

  const form = useForm<VoiceFormValues>({
    initialValues: {
      enabled: false,
      wake_word_threshold: 0.5,
      stt_model: STT_MODEL.BASE,
      stt_compute_type: STT_COMPUTE_TYPE.INT8,
      stt_language: STT_LANGUAGE.AUTO,
      tts_voice_es: "",
      tts_voice_en: "",
      vad_threshold: 0.5,
      silence_duration_ms: 1000,
    },
  });

  useEffect(() => {
    if (data) {
      form.setValues({
        enabled: data.enabled,
        wake_word_threshold: data.wake_word_threshold,
        stt_model: data.stt_model as STTModel,
        stt_compute_type: data.stt_compute_type as STTComputeType,
        stt_language: data.stt_language as STTLanguage,
        tts_voice_es: data.tts_voice_es,
        tts_voice_en: data.tts_voice_en,
        vad_threshold: data.vad_threshold,
        silence_duration_ms: data.silence_duration_ms,
      });
    }
  }, [data]);

  const handleSubmit = async (values: VoiceFormValues) => {
    setSaving(true);
    try {
      await api.updateVoice({ ...values });
      notifications.show({
        title: "Saved",
        message: "Voice settings updated",
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

  return (
    <form onSubmit={form.onSubmit(handleSubmit)}>
      <Stack gap="md">
        <Switch
          label="Enabled"
          description="Enable voice interaction"
          {...form.getInputProps("enabled", { type: "checkbox" })}
        />

        <div>
          <Text size="sm" fw={500} mb={4}>
            Wake Word Threshold
          </Text>
          <Text size="xs" c="dimmed" mb="xs">
            Sensitivity for wake word detection (0 = very sensitive, 1 = strict)
          </Text>
          <Slider
            min={0}
            max={1}
            step={0.05}
            label={(v: number) => v.toFixed(2)}
            {...form.getInputProps("wake_word_threshold")}
          />
        </div>

        <Select
          label="STT Model"
          description="Speech-to-text model size"
          data={STT_MODEL_OPTIONS}
          {...form.getInputProps("stt_model")}
        />

        <Select
          label="STT Compute Type"
          description="Computation precision"
          data={STT_COMPUTE_OPTIONS}
          {...form.getInputProps("stt_compute_type")}
        />

        <Select
          label="STT Language"
          description="Speech recognition language"
          data={STT_LANGUAGE_OPTIONS}
          {...form.getInputProps("stt_language")}
        />

        <TextInput
          label="TTS Voice (Spanish)"
          description="Voice identifier for Spanish TTS"
          {...form.getInputProps("tts_voice_es")}
        />

        <TextInput
          label="TTS Voice (English)"
          description="Voice identifier for English TTS"
          {...form.getInputProps("tts_voice_en")}
        />

        <div>
          <Text size="sm" fw={500} mb={4}>
            VAD Threshold
          </Text>
          <Text size="xs" c="dimmed" mb="xs">
            Voice Activity Detection sensitivity
          </Text>
          <Slider
            min={0}
            max={1}
            step={0.01}
            label={(v: number) => v.toFixed(2)}
            {...form.getInputProps("vad_threshold")}
          />
        </div>

        <NumberInput
          label="Silence Duration"
          description="Milliseconds of silence before ending capture"
          min={100}
          step={100}
          suffix=" ms"
          {...form.getInputProps("silence_duration_ms")}
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
