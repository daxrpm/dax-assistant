import { useEffect, useRef, useState } from "react";
import { currentToken, getWsUrl } from "../api/connection";

export type PipelineState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "conversing";

export interface LevelFrame {
  source: "input" | "output";
  rms: number[];
  peak: number;
  spectrum: number[];
}

export interface VoiceTranscript {
  text: string;
  language: string;
  final: boolean;
}

export interface SpeakerVerdict {
  verified: boolean;
  score: number | null;
}

/**
 * `/ws/voice` client (PLAN.md 4.6).
 *
 * Server → client only. The backend replays `last_state` on connect, so a
 * client attaching mid-conversation renders the true state rather than "idle".
 *
 * NOTE — level frames are intentionally NOT retained here. They arrive at
 * ~12.5/s carrying 4 RMS sub-windows each (~50 envelope points/s); routing them
 * through React state would re-render the tree 12 times a second for a purely
 * visual signal. `onLevel` hands them straight to a consumer instead.
 *
 * ┌─ INTEGRATION POINT — voice waveform (M4, out of scope here) ─────────────┐
 * │ The waveform renderer subscribes via `onLevel` and drives a Canvas loop  │
 * │ outside the reconciler, interpolating ~50 points/s up to 60 fps with a   │
 * │ spring integrator. Nothing in this hook needs to change to support it.   │
 * └─────────────────────────────────────────────────────────────────────────┘
 */
export function useVoiceSocket(options?: { onLevel?: (frame: LevelFrame) => void }) {
  const [state, setState] = useState<PipelineState>("idle");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [transcript, setTranscript] = useState<VoiceTranscript | null>(null);
  const [speaker, setSpeaker] = useState<SpeakerVerdict | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);

  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedRef = useRef(false);
  // Kept in a ref so a caller passing an inline callback does not force the
  // socket to tear down and reconnect on every render.
  const onLevelRef = useRef(options?.onLevel);
  onLevelRef.current = options?.onLevel;

  useEffect(() => {
    closedRef.current = false;

    const connect = () => {
      if (closedRef.current) return;
      const ws = new WebSocket(getWsUrl("/ws/voice", currentToken()));
      socketRef.current = ws;

      ws.onopen = () => setConnected(true);
      ws.onclose = (event) => {
        setConnected(false);
        if (event.code === 1008 || closedRef.current) return;
        retryRef.current = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        let frame: { type: string; data: Record<string, unknown> };
        try {
          frame = JSON.parse(event.data as string) as typeof frame;
        } catch {
          return;
        }

        switch (frame.type) {
          case "state":
            setState((frame.data.state as PipelineState) ?? "idle");
            setConversationId((frame.data.conversation_id as string | null) ?? null);
            break;
          case "level":
            onLevelRef.current?.(frame.data as unknown as LevelFrame);
            break;
          case "transcript":
            setTranscript(frame.data as unknown as VoiceTranscript);
            break;
          case "speaker":
            setSpeaker(frame.data as unknown as SpeakerVerdict);
            break;
          case "error":
            setError((frame.data.message as string) ?? "Voice error");
            break;
        }
      };
    };

    connect();
    return () => {
      closedRef.current = true;
      if (retryRef.current) clearTimeout(retryRef.current);
      socketRef.current?.close();
    };
  }, []);

  return { state, conversationId, transcript, speaker, error, connected };
}
