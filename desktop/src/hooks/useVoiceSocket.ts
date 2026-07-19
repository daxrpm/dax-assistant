import { useEffect, useSyncExternalStore } from "react";
import { currentToken, getWsUrl } from "../api/connection";
import { DemandLifecycle } from "../stores/demandLifecycle";

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

export interface VoiceSpeech {
  text: string;
  language: string;
}

export interface SpeakerVerdict {
  verified: boolean;
  score: number | null;
}

export interface VoiceSnapshot {
  state: PipelineState;
  conversationId: string | null;
  transcript: VoiceTranscript | null;
  speech: VoiceSpeech | null;
  speaker: SpeakerVerdict | null;
  error: string | null;
  connected: boolean;
  sessionExpiresAt: number | null;
  turns: number;
}

const INITIAL_SNAPSHOT: VoiceSnapshot = {
  state: "idle",
  conversationId: null,
  transcript: null,
  speech: null,
  speaker: null,
  error: null,
  connected: false,
  sessionExpiresAt: null,
  turns: 0,
};

export function createVoiceStore() {
  let snapshot = INITIAL_SNAPSHOT;
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;
  let stopped = true;
  let remoteAcquired = false;
  let remoteStreaming = false;
  let connectionWaiters: Array<{ resolve: () => void; reject: (error: Error) => void }> = [];
  let control: {
    expected: string;
    resolve: () => void;
    reject: (error: Error) => void;
    timer: ReturnType<typeof setTimeout>;
  } | null = null;
  const levelListeners = new Set<(frame: LevelFrame) => void>();
  const disconnectListeners = new Set<() => void>();

  const update = (patch: Partial<VoiceSnapshot>) => {
    snapshot = { ...snapshot, ...patch };
    lifecycle.emit();
  };

  const connect = () => {
    if (stopped || socket) return;
    let ws: WebSocket;
    try {
      ws = new WebSocket(getWsUrl("/ws/voice", currentToken()));
    } catch (error) {
      const failure = error instanceof Error ? error : new Error(String(error));
      for (const waiter of connectionWaiters.splice(0)) waiter.reject(failure);
      update({ error: failure.message });
      return;
    }
    socket = ws;
    ws.onopen = () => {
      update({ connected: true, error: null });
      for (const waiter of connectionWaiters.splice(0)) waiter.resolve();
    };
    ws.onclose = (event) => {
      if (socket === ws) socket = null;
      remoteAcquired = false;
      remoteStreaming = false;
      for (const listener of disconnectListeners) listener();
      const failure = new Error("Voice connection closed");
      if (control) {
        clearTimeout(control.timer);
        control.reject(failure);
        control = null;
      }
      for (const waiter of connectionWaiters.splice(0)) waiter.reject(failure);
      update({ connected: false, error: event.code === 1008 ? event.reason || failure.message : snapshot.error });
      if (event.code !== 1008 && !stopped) retry = setTimeout(connect, 2000);
    };
    ws.onerror = () => ws.close();
    ws.onmessage = (event) => {
      let frame: { type: string; data: Record<string, unknown> };
      try {
        frame = JSON.parse(event.data as string) as typeof frame;
      } catch {
        return;
      }
      if (frame.type === "level") {
        for (const listener of levelListeners) {
          listener(frame.data as unknown as LevelFrame);
        }
        return;
      }
      if (frame.type === "remote_audio.error") {
        const failure = new Error((frame.data.message as string) ?? "Remote audio error");
        if (control) {
          clearTimeout(control.timer);
          control.reject(failure);
          control = null;
        }
        update({ error: failure.message });
        return;
      }
      if (control && frame.type === control.expected) {
        clearTimeout(control.timer);
        const pending = control;
        control = null;
        pending.resolve();
        return;
      }
      if (frame.type === "state") {
        const conversationId = (frame.data.conversation_id as string | null) ?? null;
        const expires = frame.data.session_expires_at;
        const state = (frame.data.state as PipelineState) ?? "idle";
        update({
          state,
          conversationId,
          sessionExpiresAt: typeof expires === "number" ? expires : null,
          turns: snapshot.conversationId === conversationId ? snapshot.turns : 0,
          speech: state === "speaking" ? snapshot.speech : null,
        });
      } else if (frame.type === "transcript") {
        const transcript = frame.data as unknown as VoiceTranscript;
        update({ transcript, turns: snapshot.turns + (transcript.final ? 1 : 0) });
      } else if (frame.type === "speech") {
        update({ speech: frame.data as unknown as VoiceSpeech });
      } else if (frame.type === "speaker") {
        update({ speaker: frame.data as unknown as SpeakerVerdict });
      } else if (frame.type === "error") {
        update({ error: (frame.data.message as string) ?? "Voice error" });
      }
    };
  };

  const ensureConnected = async () => {
    stopped = false;
    if (snapshot.connected && socket) return;
    await new Promise<void>((resolve, reject) => {
      connectionWaiters.push({ resolve, reject });
      connect();
    });
  };

  const sendControl = async (type: string, expected: string, extra = {}) => {
    await ensureConnected();
    if (!socket || control) throw new Error("Another remote audio command is pending");
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        if (control?.timer === timer) control = null;
        reject(new Error(`Timed out waiting for ${expected}`));
      }, 5_000);
      control = { expected, resolve, reject, timer };
      socket?.send(JSON.stringify({ type, ...extra }));
    });
  };

  const lifecycle = new DemandLifecycle(
    () => {
      stopped = false;
      connect();
    },
    () => {
      stopped = true;
      if (retry) clearTimeout(retry);
      retry = null;
      const active = socket;
      socket = null;
      active?.close();
      if (snapshot.connected) update({ connected: false });
    },
    true,
  );

  return {
    subscribe: lifecycle.subscribe,
    getSnapshot: () => snapshot,
    subscribeLevel(listener: (frame: LevelFrame) => void) {
      levelListeners.add(listener);
      return () => {
        levelListeners.delete(listener);
      };
    },
    onRemoteDisconnect(listener: () => void) {
      disconnectListeners.add(listener);
      return () => disconnectListeners.delete(listener);
    },
    async acquireRemoteAudio() {
      if (remoteAcquired) return;
      await sendControl("remote_audio.acquire", "remote_audio.acquired", {
        format: { sample_rate: 16_000, channels: 1, sample_format: "pcm_s16le" },
      });
      remoteAcquired = true;
    },
    async startRemoteAudio() {
      if (!remoteAcquired) throw new Error("Remote audio is not acquired");
      await sendControl("remote_audio.start", "remote_audio.started");
      remoteStreaming = true;
    },
    async stopRemoteAudio() {
      if (!remoteStreaming) return;
      await sendControl("remote_audio.stop", "remote_audio.stopped");
      remoteStreaming = false;
    },
    async cancelRemoteAudio() {
      if (!remoteAcquired || !snapshot.connected) return;
      try {
        if (remoteStreaming) await sendControl("remote_audio.stop", "remote_audio.stopped");
        remoteStreaming = false;
        await sendControl("remote_audio.release", "remote_audio.released");
        remoteAcquired = false;
      } catch {
        socket?.close();
      }
    },
    sendPcm(frame: ArrayBuffer) {
      if (!remoteStreaming || !socket || socket.readyState !== WebSocket.OPEN) return;
      socket.send(frame);
    },
    shutdown: () => lifecycle.shutdown(),
  };
}

export type VoiceStore = ReturnType<typeof createVoiceStore>;
export const voiceStore = createVoiceStore();

export function useVoiceSocket(options?: { onLevel?: (frame: LevelFrame) => void }) {
  const snapshot = useSyncExternalStore(
    voiceStore.subscribe,
    voiceStore.getSnapshot,
    voiceStore.getSnapshot,
  );

  useEffect(() => {
    if (!options?.onLevel) return;
    return voiceStore.subscribeLevel(options.onLevel);
  }, [options?.onLevel]);

  return snapshot;
}
