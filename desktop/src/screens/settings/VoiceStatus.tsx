import { useCallback, useRef, useState } from "react";
import { api } from "../../api/client";
import { usesRemoteAudio } from "../../api/connection";
import type { FullConfig } from "../../api/types";
import { VoiceIcon } from "../../components/icons";
import {
  VoiceOrb,
  type OrbState,
  type VoiceOrbHandle,
} from "../../components/VoiceOrb";
import {
  Badge,
  Button,
  Panel,
  PanelBody,
  PanelHeader,
  useToast,
} from "../../design/primitives";
import {
  useVoiceSocket,
  type LevelFrame,
  type PipelineState,
} from "../../hooks/useVoiceSocket";
import p from "../page.module.css";
import s from "./VoiceStatus.module.css";
import { useI18n } from "../../i18n/I18n";

const STATE_TONE: Record<PipelineState, "neutral" | "accent" | "success" | "warning"> = {
  idle: "neutral",
  listening: "accent",
  processing: "warning",
  speaking: "success",
  conversing: "accent",
};

/**
 * The orb has four states; the pipeline has five. `conversing` is a turn-taking
 * supervisor state that the orb should render exactly like listening — the mic
 * is open either way, and level frames keep arriving.
 */
const ORB_STATE: Record<PipelineState, OrbState> = {
  idle: "idle",
  listening: "listening",
  processing: "processing",
  speaking: "speaking",
  conversing: "listening",
};

/**
 * Live voice pipeline state, driven by `/ws/voice`.
 *
 * The orb is the readout: pipeline state drives its resting behaviour and
 * level frames drive its amplitude. Transcripts, speaker verdicts and errors
 * sit beneath it.
 */
export function VoiceStatus({ config }: { config: FullConfig }) {
  const { text } = useI18n();
  const stateLabel: Record<PipelineState, string> = {
    idle: text("En reposo", "Idle"), listening: text("Escuchando", "Listening"),
    processing: text("Pensando", "Thinking"), speaking: text("Hablando", "Speaking"),
    conversing: text("En conversación", "In conversation"),
  };
  const toast = useToast();
  const orbRef = useRef<VoiceOrbHandle>(null);
  const onLevel = useCallback((frame: LevelFrame) => {
    orbRef.current?.setLevel(frame);
  }, []);
  const { state, transcript, speaker, error, connected } = useVoiceSocket({ onLevel });
  const [listening, setListening] = useState(config.voice.enabled);
  const [toggling, setToggling] = useState(false);

  const toggle = async () => {
    setToggling(true);
    try {
      const result = await api.toggleVoice(!listening);
      setListening(result.voice_listening);
      toast.show(result.voice_listening ? text("Escucha de voz activa", "Voice listening") : text("Escucha de voz en pausa", "Voice paused"), "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : text("No se pudo cambiar", "Toggle failed"), "danger");
    } finally {
      setToggling(false);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title={text("Estado en vivo", "Live status")}
        subtitle={text("Transmitido por la canalización de voz activa", "Streamed from the running voice pipeline")}
        actions={
          <div className={p.actions}>
            <Badge tone={connected ? "success" : "neutral"} dot>
              {connected ? text("Conectado", "Connected") : text("Fuera de línea", "Offline")}
            </Badge>
            <Button
              size="sm"
              variant={listening ? "destructive" : "secondary"}
              loading={toggling}
              onClick={() => void toggle()}
            >
              <VoiceIcon size={13} />
              {listening ? text("Pausar escucha", "Pause listening") : text("Iniciar escucha", "Start listening")}
            </Button>
          </div>
        }
      />
      <PanelBody>
        <div className={p.rows}>
          <div className={s.orbStage}>
            <VoiceOrb
              ref={orbRef}
              state={ORB_STATE[state]}
              size={160}
              ariaLabel={stateLabel[state]}
            />
            <div className={s.orbCaption}>
              <Badge tone={STATE_TONE[state]} dot>
                {stateLabel[state]}
              </Badge>
            </div>
          </div>

          {transcript && (
            <div className={s.transcript}>
              <span className={s.transcriptLang}>{transcript.language}</span>
              <span className={s.transcriptText}>{transcript.text}</span>
               {!transcript.final && <span className={p.dim}>({text("parcial", "partial")})</span>}
            </div>
          )}

          {speaker && (
            <div className={p.actions}>
              <Badge tone={speaker.verified ? "success" : "danger"}>
                 {speaker.verified ? text("Hablante verificado", "Speaker verified") : text("Hablante rechazado", "Speaker rejected")}
              </Badge>
              {speaker.score != null && (
                <span className={p.dim}>{text("puntuación", "score")} {speaker.score.toFixed(2)}</span>
              )}
            </div>
          )}

          {error && <p className={s.error}>{error}</p>}

          {usesRemoteAudio() && (
            <p className={p.hint}>
              {text(
                "Modo remoto: el micrófono de este equipo solo transmite mientras mantienes pulsado PTT. Las respuestas aparecen como texto en este equipo; la reproducción de voz remota aún no está disponible.",
                "Remote mode: this device's microphone streams only while you hold PTT. Replies appear as text on this device; remote voice playback is not available yet.",
              )}
            </p>
          )}

          {!config.voice.enabled && (
            <p className={p.hint}>
               {text("La voz está desactivada en la configuración; la canalización permanece en reposo. Actívala arriba para empezar.", "Voice is disabled in config, so the pipeline reports idle and nothing will stream. Enable it above to start.")}
            </p>
          )}
        </div>
      </PanelBody>
    </Panel>
  );
}
