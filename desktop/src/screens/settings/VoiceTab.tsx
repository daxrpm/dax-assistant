import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { FullConfig, VoicePreviewOptions } from "../../api/types";
import { PlayIcon } from "../../components/icons";
import {
  Badge,
  Button,
  Field,
  Panel,
  PanelBody,
  PanelHeader,
  Select,
  Slider,
  TextArea,
  TextInput,
  Toggle,
  useToast,
} from "../../design/primitives";
import p from "../page.module.css";
import { saveLabel, useSection } from "./useSection";
import { VoiceEnrollment } from "./VoiceEnrollment";

/**
 * Known voices per engine.
 *
 * The backend exposes no voice-listing endpoint — `POST /api/voice/preview`
 * takes whatever name you give it — so the gallery is a curated list and every
 * field also accepts free text.
 */
const VOICES: Record<string, string[]> = {
  kokoro: ["ef_dora", "em_alex", "af_heart", "af_bella", "am_michael", "bf_emma"],
  piper: ["es_ES-sharvard-medium", "en_US-lessac-medium", "en_GB-alba-medium"],
  openai: ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral", "sage"],
};

const STT_DEVICES = ["auto", "cpu", "cuda"];
const STT_COMPUTE = ["default", "int8", "int8_float16", "float16", "float32"];
const LANGUAGES = ["auto", "es", "en"];

function VoiceGallery({ config }: { config: FullConfig }) {
  const toast = useToast();
  const engine = (config.voice.tts_engine || "kokoro") as VoicePreviewOptions["engine"];
  const [playing, setPlaying] = useState<string | null>(null);
  const [text, setText] = useState("Hola, soy Dax. ¿En qué puedo ayudarte?");

  const preview = async (voice: string) => {
    setPlaying(voice);
    try {
      const blob = await api.previewVoice({
        engine,
        voice,
        text,
        language: text.match(/[áéíóúñ¿¡]/i) ? "es" : "en",
      });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      // Revoke once playback ends so long sessions do not leak blob URLs.
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        toast.show(`The ${engine} engine is not available on the server`, "danger");
      } else {
        toast.show(err instanceof Error ? err.message : "Preview failed", "danger");
      }
    } finally {
      setPlaying(null);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Voice gallery"
        subtitle={`Preview voices for the ${engine} engine`}
      />
      <PanelBody>
        <div className={p.rows}>
          <Field label="Preview text">
            {(id) => (
              <TextInput
                id={id}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            )}
          </Field>
          <div className={p.tagList}>
            {(VOICES[engine] ?? []).map((voice) => (
              <Button
                key={voice}
                size="sm"
                variant="secondary"
                loading={playing === voice}
                onClick={() => void preview(voice)}
              >
                <PlayIcon size={12} />
                {voice}
              </Button>
            ))}
          </div>
        </div>
      </PanelBody>
    </Panel>
  );
}

export function VoiceTab({
  config,
  onSaved,
}: {
  config: FullConfig;
  onSaved: () => void;
}) {
  const { draft, set, dirty, saving, commit } = useSection(
    config.voice,
    api.updateVoice,
    onSaved,
  );
  const [sttKey, setSttKey] = useState("");

  const save = () => {
    const patch: Record<string, unknown> = { ...draft };
    if (sttKey.trim()) patch.stt_openai_api_key = sttKey.trim();
    void commit(patch).then(() => setSttKey(""));
  };

  const keyDirty = sttKey.trim().length > 0;
  const saveButton = (
    <Button
      size="sm"
      variant="primary"
      loading={saving}
      disabled={(!dirty && !keyDirty) || saving}
      onClick={save}
    >
      {saveLabel(dirty || keyDirty, saving)}
    </Button>
  );

  return (
    <div className={p.rows}>
      <Panel>
        <PanelHeader
          title="Voice"
          subtitle="Wake word and activation"
          actions={saveButton}
        />
        <PanelBody>
          <div className={p.rows}>
            <Field
              label="Enabled"
              description="Starts the local voice pipeline. Changes apply live."
            >
              {(id) => (
                <Toggle
                  id={id}
                  checked={draft.enabled}
                  onChange={(v) => set("enabled", v)}
                />
              )}
            </Field>

            <div className={p.row2}>
              <Field label="Wake word model">
                {(id) => (
                  <TextInput
                    id={id}
                    value={draft.wake_word_model}
                    onChange={(e) => set("wake_word_model", e.target.value)}
                  />
                )}
              </Field>
              <Field label={`Wake word threshold — ${draft.wake_word_threshold}`}>
                {(id) => (
                  <Slider
                    id={id}
                    min={0}
                    max={1}
                    step={0.01}
                    value={draft.wake_word_threshold}
                    onChange={(v) => set("wake_word_threshold", v)}
                    format={(v) => v.toFixed(2)}
                  />
                )}
              </Field>
            </div>

            <div className={p.row2}>
              <Field
                label="Require wake word each turn"
                description="Off means follow-ups need no wake word."
              >
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.require_wake_word_each_turn}
                    onChange={(v) => set("require_wake_word_each_turn", v)}
                  />
                )}
              </Field>
              <Field
                label="Voice confirmation"
                description="Speak tool confirmations aloud."
              >
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.voice_confirm}
                    onChange={(v) => set("voice_confirm", v)}
                  />
                )}
              </Field>
            </div>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Speech to text" actions={saveButton} />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <Field label="Backend">
                {(id) => (
                  <Select
                    id={id}
                    value={draft.stt_backend}
                    onChange={(e) =>
                      set("stt_backend", e.target.value as "local" | "openai")
                    }
                  >
                    <option value="local">local (faster-whisper)</option>
                    <option value="openai">openai</option>
                  </Select>
                )}
              </Field>
              <Field label="Language">
                {(id) => (
                  <Select
                    id={id}
                    value={draft.stt_language}
                    onChange={(e) => set("stt_language", e.target.value)}
                  >
                    {LANGUAGES.map((l) => (
                      <option key={l} value={l}>
                        {l}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>

            {draft.stt_backend === "local" ? (
              <>
                <div className={p.row2}>
                  <Field label="Model">
                    {(id) => (
                      <TextInput
                        id={id}
                        value={draft.stt_model}
                        onChange={(e) => set("stt_model", e.target.value)}
                      />
                    )}
                  </Field>
                  <Field label="Beam size">
                    {(id) => (
                      <TextInput
                        id={id}
                        type="number"
                        value={draft.stt_beam_size}
                        onChange={(e) => set("stt_beam_size", Number(e.target.value))}
                      />
                    )}
                  </Field>
                </div>
                <div className={p.row2}>
                  <Field label="Device">
                    {(id) => (
                      <Select
                        id={id}
                        value={draft.stt_device}
                        onChange={(e) => set("stt_device", e.target.value)}
                      >
                        {STT_DEVICES.map((d) => (
                          <option key={d} value={d}>
                            {d}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                  <Field label="Compute type">
                    {(id) => (
                      <Select
                        id={id}
                        value={draft.stt_compute_type}
                        onChange={(e) => set("stt_compute_type", e.target.value)}
                      >
                        {STT_COMPUTE.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                </div>
              </>
            ) : (
              <>
                <div className={p.row2}>
                  <Field label="Model">
                    {(id) => (
                      <TextInput
                        id={id}
                        value={draft.stt_openai_model}
                        onChange={(e) => set("stt_openai_model", e.target.value)}
                      />
                    )}
                  </Field>
                  <Field label="Timeout (seconds)">
                    {(id) => (
                      <TextInput
                        id={id}
                        type="number"
                        value={draft.stt_openai_timeout_s}
                        onChange={(e) =>
                          set("stt_openai_timeout_s", Number(e.target.value))
                        }
                      />
                    )}
                  </Field>
                </div>

                <Field
                  label="API key"
                  description={
                    draft.stt_openai_configured
                      ? "Configured. Leave blank to keep the stored key."
                      : "Falls back to the general OpenAI key when blank."
                  }
                >
                  {(id) => (
                    <TextInput
                      id={id}
                      type="password"
                      value={sttKey}
                      placeholder={draft.stt_openai_configured ? "••••••••" : "sk-…"}
                      onChange={(e) => setSttKey(e.target.value)}
                    />
                  )}
                </Field>

                <Field
                  label="Prompt vocabulary"
                  description="Names and jargon to bias transcription toward."
                >
                  {(id) => (
                    <TextArea
                      id={id}
                      rows={2}
                      value={draft.stt_openai_prompt}
                      onChange={(e) => set("stt_openai_prompt", e.target.value)}
                    />
                  )}
                </Field>

                <Field
                  label="Fall back to local"
                  description="Use faster-whisper when the API call fails."
                >
                  {(id) => (
                    <Toggle
                      id={id}
                      checked={draft.stt_fallback_to_local}
                      onChange={(v) => set("stt_fallback_to_local", v)}
                    />
                  )}
                </Field>
              </>
            )}
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader title="Text to speech" actions={saveButton} />
        <PanelBody>
          <div className={p.rows}>
            <Field label="Engine">
              {(id) => (
                <Select
                  id={id}
                  value={draft.tts_engine}
                  onChange={(e) => set("tts_engine", e.target.value)}
                >
                  <option value="kokoro">kokoro</option>
                  <option value="piper">piper</option>
                  <option value="openai">openai</option>
                </Select>
              )}
            </Field>

            {draft.tts_engine === "kokoro" && (
              <>
                <div className={p.row2}>
                  <Field label="Spanish voice">
                    {(id) => (
                      <TextInput
                        id={id}
                        value={draft.tts_kokoro_voice_es}
                        onChange={(e) => set("tts_kokoro_voice_es", e.target.value)}
                      />
                    )}
                  </Field>
                  <Field label="English voice">
                    {(id) => (
                      <TextInput
                        id={id}
                        value={draft.tts_kokoro_voice_en}
                        onChange={(e) => set("tts_kokoro_voice_en", e.target.value)}
                      />
                    )}
                  </Field>
                </div>
                <Field label={`Speed — ${draft.tts_kokoro_speed}×`}>
                  {(id) => (
                    <Slider
                      id={id}
                      min={0.5}
                      max={2}
                      step={0.05}
                      value={draft.tts_kokoro_speed}
                      onChange={(v) => set("tts_kokoro_speed", v)}
                      format={(v) => `${v.toFixed(2)}×`}
                    />
                  )}
                </Field>
              </>
            )}

            {draft.tts_engine === "piper" && (
              <div className={p.row2}>
                <Field label="Spanish voice">
                  {(id) => (
                    <TextInput
                      id={id}
                      value={draft.tts_voice_es}
                      onChange={(e) => set("tts_voice_es", e.target.value)}
                    />
                  )}
                </Field>
                <Field label="English voice">
                  {(id) => (
                    <TextInput
                      id={id}
                      value={draft.tts_voice_en}
                      onChange={(e) => set("tts_voice_en", e.target.value)}
                    />
                  )}
                </Field>
              </div>
            )}

            {draft.tts_engine === "openai" && (
              <>
                <div className={p.row2}>
                  <Field label="Model">
                    {(id) => (
                      <TextInput
                        id={id}
                        value={draft.tts_openai_model}
                        onChange={(e) => set("tts_openai_model", e.target.value)}
                      />
                    )}
                  </Field>
                  <Field label="Voice">
                    {(id) => (
                      <Select
                        id={id}
                        value={draft.tts_openai_voice}
                        onChange={(e) => set("tts_openai_voice", e.target.value)}
                      >
                        {(VOICES.openai ?? []).map((v) => (
                          <option key={v} value={v}>
                            {v}
                          </option>
                        ))}
                      </Select>
                    )}
                  </Field>
                </div>
                <div className={p.row2}>
                  <Field label="Spanish instructions">
                    {(id) => (
                      <TextArea
                        id={id}
                        rows={2}
                        value={draft.tts_openai_instructions_es}
                        onChange={(e) =>
                          set("tts_openai_instructions_es", e.target.value)
                        }
                      />
                    )}
                  </Field>
                  <Field label="English instructions">
                    {(id) => (
                      <TextArea
                        id={id}
                        rows={2}
                        value={draft.tts_openai_instructions_en}
                        onChange={(e) =>
                          set("tts_openai_instructions_en", e.target.value)
                        }
                      />
                    )}
                  </Field>
                </div>
                <Field label="Timeout (seconds)">
                  {(id) => (
                    <TextInput
                      id={id}
                      type="number"
                      value={draft.tts_openai_timeout_s}
                      onChange={(e) =>
                        set("tts_openai_timeout_s", Number(e.target.value))
                      }
                    />
                  )}
                </Field>
              </>
            )}

            <Field
              label="Fall back to local TTS"
              description="Use the local engine when the remote one fails."
            >
              {(id) => (
                <Toggle
                  id={id}
                  checked={draft.tts_fallback_to_local}
                  onChange={(v) => set("tts_fallback_to_local", v)}
                />
              )}
            </Field>
          </div>
        </PanelBody>
      </Panel>

      <VoiceGallery config={config} />

      <Panel>
        <PanelHeader
          title="Listening and turn taking"
          subtitle="Endpointing, barge-in and conversation timing"
          actions={saveButton}
        />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <Field label={`VAD threshold — ${draft.vad_threshold}`}>
                {(id) => (
                  <Slider
                    id={id}
                    min={0}
                    max={1}
                    step={0.01}
                    value={draft.vad_threshold}
                    onChange={(v) => set("vad_threshold", v)}
                    format={(v) => v.toFixed(2)}
                  />
                )}
              </Field>
              <Field label="Silence duration (ms)">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    value={draft.silence_duration_ms}
                    onChange={(e) => set("silence_duration_ms", Number(e.target.value))}
                  />
                )}
              </Field>
            </div>

            <div className={p.row2}>
              <Field
                label="Adaptive endpointing"
                description="Tune the silence window to the speaker's cadence."
              >
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.adaptive_endpointing}
                    onChange={(v) => set("adaptive_endpointing", v)}
                  />
                )}
              </Field>
              <Field label="Denoise" description="Filter the mic input before STT.">
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.denoise}
                    onChange={(v) => set("denoise", v)}
                  />
                )}
              </Field>
            </div>

            <div className={p.row2}>
              <Field
                label="Barge-in"
                description="Let the user interrupt playback by speaking."
              >
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.barge_in}
                    onChange={(v) => set("barge_in", v)}
                  />
                )}
              </Field>
              <Field label="Earcon" description="Play a chime on wake.">
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.earcon}
                    onChange={(v) => set("earcon", v)}
                  />
                )}
              </Field>
            </div>

            <div className={p.row2}>
              <Field label="Conversation timeout (seconds)">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    value={draft.conversation_timeout_s}
                    onChange={(e) =>
                      set("conversation_timeout_s", Number(e.target.value))
                    }
                  />
                )}
              </Field>
              <Field label="Follow-up activation (ms)">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    value={draft.followup_activation_ms}
                    onChange={(e) =>
                      set("followup_activation_ms", Number(e.target.value))
                    }
                  />
                )}
              </Field>
            </div>

            <div className={p.row2}>
              <Field label="Thinking pause (ms)">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    value={draft.thinking_pause_ms}
                    onChange={(e) => set("thinking_pause_ms", Number(e.target.value))}
                  />
                )}
              </Field>
              <Field label="Response timeout (seconds)">
                {(id) => (
                  <TextInput
                    id={id}
                    type="number"
                    value={draft.response_timeout_s}
                    onChange={(e) => set("response_timeout_s", Number(e.target.value))}
                  />
                )}
              </Field>
            </div>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader
          title="Speaker verification"
          subtitle="Only respond to an enrolled voice"
          actions={
            <div className={p.actions}>
              {draft.speaker_profile_enrolled && (
                <Badge tone="success" dot>
                  Profile enrolled
                </Badge>
              )}
              {saveButton}
            </div>
          }
        />
        <PanelBody>
          <div className={p.rows}>
            <div className={p.row2}>
              <Field label="Enabled">
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.speaker_verification}
                    onChange={(v) => set("speaker_verification", v)}
                  />
                )}
              </Field>
              <Field
                label="Fail open"
                description="Accept the turn when verification cannot run."
              >
                {(id) => (
                  <Toggle
                    id={id}
                    checked={draft.speaker_fail_open}
                    onChange={(v) => set("speaker_fail_open", v)}
                  />
                )}
              </Field>
            </div>

            <Field label={`Match threshold — ${draft.speaker_threshold}`}>
              {(id) => (
                <Slider
                  id={id}
                  min={0}
                  max={1}
                  step={0.01}
                  value={draft.speaker_threshold}
                  onChange={(v) => set("speaker_threshold", v)}
                  format={(v) => v.toFixed(2)}
                />
              )}
            </Field>
          </div>
        </PanelBody>
      </Panel>

      <VoiceEnrollment />
    </div>
  );
}
