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
  const [wakeModel, setWakeModel] = useState(v.wake_word_model);
  const [sttBackend, setSttBackend] = useState(v.stt_backend ?? "local");
  const [sttModel, setSttModel] = useState(v.stt_model);
  const [sttLang, setSttLang] = useState(v.stt_language);
  const [sttDevice, setSttDevice] = useState(v.stt_device ?? "auto");
  const [sttCompute, setSttCompute] = useState(v.stt_compute_type ?? "auto");
  const [sttBeam, setSttBeam] = useState(v.stt_beam_size ?? 2);
  const [openAIModel, setOpenAIModel] = useState(v.stt_openai_model);
  const [openAIKey, setOpenAIKey] = useState("");
  const [openAITimeout, setOpenAITimeout] = useState(v.stt_openai_timeout_s);
  const [openAIPrompt, setOpenAIPrompt] = useState(v.stt_openai_prompt);
  const [localFallback, setLocalFallback] = useState(v.stt_fallback_to_local);
  const [ttsEngine, setTTSEngine] = useState(v.tts_engine);
  const [piperVoiceEs, setPiperVoiceEs] = useState(v.tts_voice_es);
  const [piperVoiceEn, setPiperVoiceEn] = useState(v.tts_voice_en);
  const [kokoroVoiceEs, setKokoroVoiceEs] = useState(v.tts_kokoro_voice_es);
  const [kokoroVoiceEn, setKokoroVoiceEn] = useState(v.tts_kokoro_voice_en);
  const [kokoroSpeed, setKokoroSpeed] = useState(v.tts_kokoro_speed);
  const [wakeThreshold, setWakeThreshold] = useState(v.wake_word_threshold);
  const [vadThreshold, setVadThreshold] = useState(v.vad_threshold);
  const [silence, setSilence] = useState(v.silence_duration_ms);
  const [adaptive, setAdaptive] = useState(v.adaptive_endpointing ?? true);
  const [denoise, setDenoise] = useState(v.denoise ?? true);
  const [bargeIn, setBargeIn] = useState(v.barge_in ?? true);
  const [earcon, setEarcon] = useState(v.earcon ?? true);
  const [conversationTimeout, setConversationTimeout] = useState(v.conversation_timeout_s);
  const [responseTimeout, setResponseTimeout] = useState(v.response_timeout_s);
  const [voiceConfirm, setVoiceConfirm] = useState(v.voice_confirm);
  const [wakeEachTurn, setWakeEachTurn] = useState(v.require_wake_word_each_turn);
  const [speakerVerification, setSpeakerVerification] = useState(v.speaker_verification);
  const [speakerThreshold, setSpeakerThreshold] = useState(v.speaker_threshold);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateVoice({
        enabled,
        wake_word_model: wakeModel,
        stt_backend: sttBackend,
        stt_model: sttModel,
        stt_language: sttLang,
        stt_device: sttDevice,
        stt_compute_type: sttCompute,
        stt_beam_size: sttBeam,
        stt_openai_model: openAIModel,
        stt_openai_timeout_s: openAITimeout,
        stt_openai_prompt: openAIPrompt,
        stt_openai_api_key: openAIKey || undefined,
        stt_fallback_to_local: localFallback,
        tts_engine: ttsEngine,
        tts_voice_es: piperVoiceEs,
        tts_voice_en: piperVoiceEn,
        tts_kokoro_voice_es: kokoroVoiceEs,
        tts_kokoro_voice_en: kokoroVoiceEn,
        tts_kokoro_speed: kokoroSpeed,
        wake_word_threshold: wakeThreshold,
        vad_threshold: vadThreshold,
        silence_duration_ms: silence,
        adaptive_endpointing: adaptive,
        denoise,
        barge_in: bargeIn,
        earcon,
        conversation_timeout_s: conversationTimeout,
        response_timeout_s: responseTimeout,
        voice_confirm: voiceConfirm,
        require_wake_word_each_turn: wakeEachTurn,
        speaker_verification: speakerVerification,
        speaker_threshold: speakerThreshold,
      });
      setOpenAIKey("");
      toast.show("Voice settings saved and pipeline reloaded", "success");
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
        <Field label="Wake word model" description="Built-in name such as hey_jarvis or alexa, or a custom ONNX path.">
          <TextInput value={wakeModel} onChange={(e) => setWakeModel(e.target.value)} />
        </Field>
        <Field
          label="Speech-to-text backend"
          description={sttBackend === "local" ? "Runs privately on this machine." : "Uploads each completed utterance to OpenAI."}
        >
          <Select value={sttBackend} onChange={(e) => setSttBackend(e.target.value as "local" | "openai")}>
            <option value="local">Local faster-whisper</option>
            <option value="openai">OpenAI hosted</option>
          </Select>
        </Field>
        {sttBackend === "local" ? (
          <>
            <Field label="Local STT model">
              <Select value={sttModel} onChange={(e) => setSttModel(e.target.value)}>
                {["tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"].map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </Select>
            </Field>
            <Field label="Local decoding beam" description="Two balances accuracy and CPU latency.">
              <TextInput type="number" min="1" max="10" value={sttBeam} onChange={(e) => setSttBeam(Number(e.target.value))} />
            </Field>
            <Field label="STT device" description="Auto uses GPU float16 when available, otherwise CPU int8.">
              <Select value={sttDevice} onChange={(e) => setSttDevice(e.target.value)}>
                <option value="auto">Auto</option>
                <option value="cpu">CPU</option>
                <option value="cuda">GPU (CUDA)</option>
              </Select>
            </Field>
            <Field label="Compute type" description="Auto selects float16 on CUDA and int8 on CPU.">
              <Select value={sttCompute} onChange={(e) => setSttCompute(e.target.value)}>
                <option value="auto">Auto</option>
                <option value="int8">int8</option>
                <option value="float16">float16</option>
                <option value="float32">float32</option>
              </Select>
            </Field>
          </>
        ) : (
          <>
            <Field label="OpenAI transcription model">
              <Select value={openAIModel} onChange={(e) => setOpenAIModel(e.target.value)}>
                <option value="gpt-4o-mini-transcribe">GPT-4o mini transcribe</option>
                <option value="gpt-4o-transcribe">GPT-4o transcribe</option>
                <option value="whisper-1">Whisper hosted</option>
              </Select>
            </Field>
            <Field label="OpenAI API key" description={v.stt_openai_configured ? "Configured. Leave blank to keep the stored key." : "Required for hosted transcription; stored encrypted."}>
              <TextInput type="password" value={openAIKey} placeholder={v.stt_openai_configured ? "••••••••" : "sk-..."} onChange={(e) => setOpenAIKey(e.target.value)} />
            </Field>
            <Field label="Hosted timeout (seconds)">
              <TextInput type="number" min="1" max="120" value={openAITimeout} onChange={(e) => setOpenAITimeout(Number(e.target.value))} />
            </Field>
            <Field label="Transcription vocabulary" description="Context improves names, services and uncommon commands.">
              <TextInput value={openAIPrompt} onChange={(e) => setOpenAIPrompt(e.target.value)} />
            </Field>
            <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
              <div><p className="text-sm font-medium">Local fallback</p><p className="text-xs text-muted">Use faster-whisper if OpenAI or the network fails</p></div>
              <Toggle checked={localFallback} onChange={setLocalFallback} label="Local fallback" />
            </div>
          </>
        )}
        <Field label="STT language">
          <Select value={sttLang} onChange={(e) => setSttLang(e.target.value)}>
            <option value="auto">Auto</option>
            <option value="es">Spanish</option>
            <option value="en">English</option>
          </Select>
        </Field>
        <Field label="Text-to-speech engine" description="Kokoro is more natural; Piper is lighter and faster.">
          <Select value={ttsEngine} onChange={(e) => setTTSEngine(e.target.value)}>
            <option value="kokoro">Kokoro neural</option>
            <option value="piper">Piper local</option>
          </Select>
        </Field>
        {ttsEngine === "kokoro" ? (
          <>
            <Field label="Kokoro Spanish voice">
              <TextInput value={kokoroVoiceEs} onChange={(e) => setKokoroVoiceEs(e.target.value)} />
            </Field>
            <Field label="Kokoro English voice">
              <TextInput value={kokoroVoiceEn} onChange={(e) => setKokoroVoiceEn(e.target.value)} />
            </Field>
            <Field label="Kokoro speech speed">
              <TextInput type="number" min="0.5" max="2" step="0.05" value={kokoroSpeed} onChange={(e) => setKokoroSpeed(Number(e.target.value))} />
            </Field>
          </>
        ) : (
          <>
            <Field label="Piper Spanish voice">
              <TextInput value={piperVoiceEs} onChange={(e) => setPiperVoiceEs(e.target.value)} />
            </Field>
            <Field label="Piper English voice">
              <TextInput value={piperVoiceEn} onChange={(e) => setPiperVoiceEn(e.target.value)} />
            </Field>
          </>
        )}
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
        <Field label="Follow-up window (seconds)" description="Keep listening without requiring the wake word again.">
          <TextInput type="number" min="1" max="60" value={conversationTimeout} onChange={(e) => setConversationTimeout(Number(e.target.value))} />
        </Field>
        <Field label="Maximum response wait (seconds)" description="Allows long tool actions to finish before timing out.">
          <TextInput type="number" min="10" max="600" value={responseTimeout} onChange={(e) => setResponseTimeout(Number(e.target.value))} />
        </Field>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div><p className="text-sm font-medium">Spoken confirmations</p><p className="text-xs text-muted">Approve protected actions without opening the dashboard</p></div>
          <Toggle checked={voiceConfirm} onChange={setVoiceConfirm} label="Spoken confirmations" />
        </div>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div><p className="text-sm font-medium">Wake word every turn</p><p className="text-xs text-muted">Safer in noisy or shared rooms</p></div>
          <Toggle checked={wakeEachTurn} onChange={setWakeEachTurn} label="Wake word every turn" />
        </div>
        <div className="flex items-center justify-between rounded-xl border border-separator bg-background px-3 py-2.5">
          <div><p className="text-sm font-medium">Speaker verification</p><p className="text-xs text-muted">Use the enrolled voice profile when available</p></div>
          <Toggle checked={speakerVerification} onChange={setSpeakerVerification} label="Speaker verification" />
        </div>
        {speakerVerification && (
          <Field label="Speaker acceptance threshold" description="Higher values are stricter. Enroll with scripts/enroll_voice.py first.">
            <TextInput type="number" min="0" max="1" step="0.01" value={speakerThreshold} onChange={(e) => setSpeakerThreshold(Number(e.target.value))} />
          </Field>
        )}

        <div className="flex justify-end">
          <Button variant="primary" onPress={save} isDisabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>
    </Panel>
  );
}
