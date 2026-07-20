import { useState } from "react";
import { ApiError, api } from "../../api/client";
import type { FullConfig, VoicePreviewOptions } from "../../api/types";
import { PlayIcon } from "../../components/icons";
import { Button, Field, Panel, PanelBody, PanelHeader, Select, TextInput, useToast } from "../../design/primitives";
import { useI18n } from "../../i18n/I18n";
import p from "../page.module.css";

const VOICES: Record<VoicePreviewOptions["engine"], string[]> = {
  kokoro: ["ef_dora", "em_alex", "af_heart", "af_bella", "am_michael", "bf_emma"],
  piper: ["es_ES-sharvard-medium", "en_US-lessac-medium", "en_GB-alba-medium"],
  openai: ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral", "sage"],
};

export function VoiceGallery({ config }: { config: FullConfig }) {
  const { text } = useI18n();
  const toast = useToast();
  const [engine, setEngine] = useState<VoicePreviewOptions["engine"]>(
    config.voice.tts_engine === "piper" || config.voice.tts_engine === "openai"
      ? config.voice.tts_engine
      : "kokoro",
  );
  const [language, setLanguage] = useState<"es" | "en">("es");
  const [previewText, setPreviewText] = useState("Hola, soy Dax. ¿En qué puedo ayudarte?");
  const [playing, setPlaying] = useState<string | null>(null);

  const preview = async (voice: string) => {
    setPlaying(voice);
    let url: string | null = null;
    try {
      const blob = await api.previewVoice({
        engine,
        voice,
        language,
        text: previewText,
        speed: engine === "kokoro" ? config.voice.tts_kokoro_speed : undefined,
        model: engine === "openai" ? config.voice.tts_openai_model : undefined,
        instructions: engine === "openai"
          ? language === "es"
            ? config.voice.tts_openai_instructions_es
            : config.voice.tts_openai_instructions_en
          : undefined,
      });
      url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {
        if (url) URL.revokeObjectURL(url);
      };
      await audio.play();
    } catch (error) {
      if (url) URL.revokeObjectURL(url);
      const message = error instanceof ApiError && error.status === 503
        ? text("El motor de voz no está disponible en el servidor.", "The voice engine is unavailable on the server.")
        : error instanceof Error ? error.message : text("Falló la vista previa.", "Preview failed.");
      toast.show(message, "danger");
    } finally {
      setPlaying(null);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title={text("Galería de voces", "Voice gallery")}
        subtitle={text("Escucha una voz antes de guardarla.", "Listen to a voice before saving it.")}
      />
      <PanelBody>
        <div className={p.rows}>
          <div className={p.row2}>
            <Field label={text("Motor", "Engine")}>
              {(id) => (
                <Select id={id} value={engine} onChange={(event) => setEngine(event.target.value as VoicePreviewOptions["engine"])}>
                  <option value="kokoro">Kokoro</option>
                  <option value="piper">Piper</option>
                  <option value="openai">OpenAI</option>
                </Select>
              )}
            </Field>
            <Field label={text("Idioma", "Language")}>
              {(id) => (
                <Select id={id} value={language} onChange={(event) => setLanguage(event.target.value as "es" | "en")}>
                  <option value="es">Español</option>
                  <option value="en">English</option>
                </Select>
              )}
            </Field>
          </div>
          <Field label={text("Texto de prueba", "Preview text")}>
            {(id) => <TextInput id={id} value={previewText} onChange={(event) => setPreviewText(event.target.value)} />}
          </Field>
          <div className={p.tagList}>
            {VOICES[engine].map((voice) => (
              <Button key={voice} size="sm" variant="secondary" loading={playing === voice} onClick={() => void preview(voice)}>
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
