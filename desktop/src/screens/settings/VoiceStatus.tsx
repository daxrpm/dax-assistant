import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { FullConfig } from "../../api/types";
import { VoiceIcon } from "../../components/icons";
import { VoiceOrb, type OrbState } from "../../components/VoiceOrb";
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

const STATE_TONE: Record<PipelineState, "neutral" | "accent" | "success" | "warning"> = {
  idle: "neutral",
  listening: "accent",
  processing: "warning",
  speaking: "success",
  conversing: "accent",
};

const STATE_LABEL: Record<PipelineState, string> = {
  idle: "Idle",
  listening: "Listening",
  processing: "Thinking",
  speaking: "Speaking",
  conversing: "In conversation",
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
 * Turn `/ws/voice` level frames into a `level` prop without re-rendering on
 * every frame.
 *
 * Frames arrive at ~12.5 Hz (PLAN.md 4.6). Pushing each one straight into
 * state would re-render this subtree 12 times a second for a purely visual
 * signal, which is exactly what `useVoiceSocket` warns against. Instead the
 * latest value is parked in a ref and committed at most once per animation
 * frame, so React sees at most display-rate updates and never more work than
 * the orb is already doing. The orb's own spring does the smoothing.
 */
function useOrbLevel() {
  const [level, setLevel] = useState(0);
  const pendingRef = useRef(0);
  const rafRef = useRef(0);

  const onLevel = useCallback((frame: LevelFrame) => {
    // `peak` is already normalized 0–1 and tracks transients better than the
    // mean of the four RMS sub-windows, which is what the orb wants.
    const next = Number.isFinite(frame.peak)
      ? frame.peak
      : frame.rms.reduce((a, b) => a + b, 0) / (frame.rms.length || 1);
    pendingRef.current = Math.max(0, Math.min(1, next));
    if (rafRef.current) return;
    rafRef.current = requestAnimationFrame(() => {
      rafRef.current = 0;
      setLevel(pendingRef.current);
    });
  }, []);

  useEffect(
    () => () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  return { level, onLevel };
}

/**
 * Live voice pipeline state, driven by `/ws/voice`.
 *
 * The orb is the readout: pipeline state drives its resting behaviour and
 * level frames drive its amplitude. Transcripts, speaker verdicts and errors
 * sit beneath it.
 */
export function VoiceStatus({ config }: { config: FullConfig }) {
  const toast = useToast();
  const { level, onLevel } = useOrbLevel();
  const { state, transcript, speaker, error, connected } = useVoiceSocket({ onLevel });
  const [listening, setListening] = useState(config.voice.enabled);
  const [toggling, setToggling] = useState(false);

  const toggle = async () => {
    setToggling(true);
    try {
      const result = await api.toggleVoice(!listening);
      setListening(result.voice_listening);
      toast.show(result.voice_listening ? "Voice listening" : "Voice paused", "success");
    } catch (err) {
      toast.show(err instanceof Error ? err.message : "Toggle failed", "danger");
    } finally {
      setToggling(false);
    }
  };

  return (
    <Panel>
      <PanelHeader
        title="Live status"
        subtitle="Streamed from the running voice pipeline"
        actions={
          <div className={p.actions}>
            <Badge tone={connected ? "success" : "neutral"} dot>
              {connected ? "Connected" : "Offline"}
            </Badge>
            <Button
              size="sm"
              variant={listening ? "destructive" : "secondary"}
              loading={toggling}
              onClick={() => void toggle()}
            >
              <VoiceIcon size={13} />
              {listening ? "Pause listening" : "Start listening"}
            </Button>
          </div>
        }
      />
      <PanelBody>
        <div className={p.rows}>
          <div className={s.orbStage}>
            <VoiceOrb state={ORB_STATE[state]} level={level} size={160} />
            <div className={s.orbCaption}>
              <Badge tone={STATE_TONE[state]} dot>
                {STATE_LABEL[state]}
              </Badge>
            </div>
          </div>

          {transcript && (
            <div className={s.transcript}>
              <span className={s.transcriptLang}>{transcript.language}</span>
              <span className={s.transcriptText}>{transcript.text}</span>
              {!transcript.final && <span className={p.dim}>(partial)</span>}
            </div>
          )}

          {speaker && (
            <div className={p.actions}>
              <Badge tone={speaker.verified ? "success" : "danger"}>
                {speaker.verified ? "Speaker verified" : "Speaker rejected"}
              </Badge>
              {speaker.score != null && (
                <span className={p.dim}>score {speaker.score.toFixed(2)}</span>
              )}
            </div>
          )}

          {error && <p className={s.error}>{error}</p>}

          {!config.voice.enabled && (
            <p className={p.hint}>
              Voice is disabled in config, so the pipeline reports idle and nothing will
              stream. Enable it above to start.
            </p>
          )}
        </div>
      </PanelBody>
    </Panel>
  );
}
