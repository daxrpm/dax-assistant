import { useState } from "react";
import { Button } from "@heroui/react";
import { api } from "../../api/client";
import type { FullConfig } from "../../types/config";
import {
  Panel,
  PanelHeader,
  Field,
  TextInput,
  Select,
  Toggle,
  useToast,
} from "../../components/ui";

export function VoiceTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const toast = useToast();
  const v = config.voice;
  const [enabled, setEnabled] = useState(v.enabled);
  const [sttModel, setSttModel] = useState(v.stt_model);
  const [sttLang, setSttLang] = useState(v.stt_language);
  const [wakeThreshold, setWakeThreshold] = useState(v.wake_word_threshold);
  const [vadThreshold, setVadThreshold] = useState(v.vad_threshold);
  const [silence, setSilence] = useState(v.silence_duration_ms);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateVoice({
        enabled,
        stt_model: sttModel,
        stt_language: sttLang,
        wake_word_threshold: wakeThreshold,
        vad_threshold: vadThreshold,
        silence_duration_ms: silence,
      });
      toast.show("Voice settings saved (restart to apply)", "success");
      onSaved();
    } catch (e) {
      toast.show(e instanceof Error ? e.message : "Save failed", "danger");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Panel>
      <PanelHeader title="Voice" description="Wake word, speech-to-text and VAD" />
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Voice pipeline</p>
            <p className="text-xs text-muted">Listen for the wake word</p>
          </div>
          <Toggle checked={enabled} onChange={setEnabled} label="Voice enabled" />
        </div>
        <Field label="STT model">
          <Select value={sttModel} onChange={(e) => setSttModel(e.target.value)}>
            {["tiny", "base", "small", "medium", "large-v3"].map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="STT language">
          <Select value={sttLang} onChange={(e) => setSttLang(e.target.value)}>
            <option value="auto">Auto</option>
            <option value="es">Spanish</option>
            <option value="en">English</option>
          </Select>
        </Field>
        <Field label="Wake-word threshold">
          <TextInput
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={wakeThreshold}
            onChange={(e) => setWakeThreshold(Number(e.target.value))}
          />
        </Field>
        <Field label="VAD threshold">
          <TextInput
            type="number"
            step="0.05"
            min="0"
            max="1"
            value={vadThreshold}
            onChange={(e) => setVadThreshold(Number(e.target.value))}
          />
        </Field>
        <Field label="Silence duration (ms)">
          <TextInput
            type="number"
            value={silence}
            onChange={(e) => setSilence(Number(e.target.value))}
          />
        </Field>
        <div className="flex justify-end">
          <Button variant="primary" onPress={save} isDisabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
