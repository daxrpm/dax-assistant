import { useEffect, useSyncExternalStore } from "react";
import type { PipelineState } from "../hooks/useVoiceSocket";
import { voiceStore } from "../hooks/useVoiceSocket";
import { isTauriRuntime } from "./environment";
import { setMediaDucking, type MediaDuckingState } from "./media";

export const MEDIA_DUCKING_STORAGE_KEY = "dax.media-ducking";
const CHANGE_EVENT = "dax:media-ducking-change";

export function getMediaDuckingEnabled(): boolean {
  return localStorage.getItem(MEDIA_DUCKING_STORAGE_KEY) !== "false";
}

export function setMediaDuckingEnabled(enabled: boolean): void {
  localStorage.setItem(MEDIA_DUCKING_STORAGE_KEY, String(enabled));
  window.dispatchEvent(new Event(CHANGE_EVENT));
  if (!enabled && isTauriRuntime()) void dispatchDucking("idle");
}

export function subscribeMediaDucking(listener: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, listener);
  return () => window.removeEventListener(CHANGE_EVENT, listener);
}

export function useMediaDuckingEnabled(): boolean {
  return useSyncExternalStore(subscribeMediaDucking, getMediaDuckingEnabled, () => true);
}

export function mapVoiceToDuckingState(state: PipelineState): MediaDuckingState {
  return state === "conversing" ? "processing" : state;
}

export function createDuckingDispatcher(
  send: (state: MediaDuckingState) => Promise<unknown>,
) {
  let requested: MediaDuckingState | null = null;
  let queue = Promise.resolve();
  return (state: MediaDuckingState) => {
    if (state === requested) return queue;
    requested = state;
    queue = queue.then(async () => {
      try {
        await send(state);
      } catch {
        if (requested === state) requested = null;
      }
    });
    return queue;
  };
}

const dispatchDucking = createDuckingDispatcher(setMediaDucking);

export function MediaDuckingBridge() {
  const voice = useSyncExternalStore(
    voiceStore.subscribe,
    voiceStore.getSnapshot,
    voiceStore.getSnapshot,
  );
  const enabled = useMediaDuckingEnabled();

  useEffect(() => {
    if (!isTauriRuntime()) return;
    void dispatchDucking(enabled ? mapVoiceToDuckingState(voice.state) : "idle");
  }, [enabled, voice.state]);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    const restore = () => void dispatchDucking("idle");
    window.addEventListener("pagehide", restore);
    return () => {
      window.removeEventListener("pagehide", restore);
      restore();
    };
  }, []);

  return null;
}
