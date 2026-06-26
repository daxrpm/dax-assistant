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
  const [sttDevice, setSttDevice] = useState(v.stt_device ?? "auto");
  const [wakeThreshold, setWakeThreshold] = useState(v.wake_word_threshold);
  const [vadThreshold, setVadThreshold] = useState(v.vad_threshold);
  const [silence, setSilence] = useState(v.silence_duration_ms);
  const [adaptive, setAdaptive] = useState(v.adaptive_endpointing ?? true);
  const [denoise, setDenoise] = useState(v.denoise ?? true);
  const [bargeIn, setBargeIn] = useState(v.barge_in ?? true);
  const [earcon, setEarcon] = useState(v.earcon ?? true);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateVoice({
        enabled,
        stt_model: sttModel,
        stt_language: sttLang,
        stt_device: sttDevice,
        wake_word_threshold: wakeThreshold,
        vad_threshold: vadThreshold,
        silence_duration_ms: silence,
        adaptive_endpointing: adaptive,
        denoise,
        barge_in: bargeIn,
        earcon,
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
        <Field
          label="STT device"
          description="Auto uses the GPU (float16) when available, else CPU (int8)."
        >
          <Select value={sttDevice} onChange={(e) => setSttDevice(e.target.value)}>
            <option value="auto">Auto</option>
            <option value="cpu">CPU</option>
            <option value="cuda">GPU (CUDA)</option>
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
        <Field
          label="Silence duration (ms)"
          description="End-of-speech pause. With adaptive endpointing this is the baseline."
        >
          <TextInput
            type="number"
            value={silence}
            onChange={(e) => setSilence(Number(e.target.value))}
          />
        </Field>

        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Adaptive endpointing</p>
            <p className="text-xs text-muted">Shorter pause for quick commands, longer for long ones</p>
          </div>
          <Toggle checked={adaptive} onChange={setAdaptive} label="Adaptive endpointing" />
        </div>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Noise suppression</p>
            <p className="text-xs text-muted">Clean background noise before transcribing</p>
          </div>
          <Toggle checked={denoise} onChange={setDenoise} label="Denoise" />
        </div>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Barge-in</p>
            <p className="text-xs text-muted">Interrupt Dax mid-reply by saying the wake word</p>
          </div>
          <Toggle checked={bargeIn} onChange={setBargeIn} label="Barge-in" />
        </div>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div>
            <p className="text-sm font-medium">Wake earcon</p>
            <p className="text-xs text-muted">Play a tone the instant the wake word fires</p>
          </div>
          <Toggle checked={earcon} onChange={setEarcon} label="Wake earcon" />
        </div>

        <div className="flex justify-end">
          <Button variant="primary" onPress={save} isDisabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
