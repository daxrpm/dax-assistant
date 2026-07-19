import { useEffect, useSyncExternalStore } from "react";
import type { PipelineState } from "../hooks/useVoiceSocket";
import { voiceStore } from "../hooks/useVoiceSocket";
import { isTauriRuntime } from "./environment";
import { setMediaDucking, type MediaDuckingState } from "./media";

export const MEDIA_DUCKING_STORAGE_KEY = "dax.media-ducking";
export const MEDIA_DUCKING_LEVEL_STORAGE_KEY = "dax.media-ducking-level";
export const DEFAULT_MEDIA_DUCKING_LEVEL = 0.40;
const CHANGE_EVENT = "dax:media-ducking-change";

export function getMediaDuckingEnabled(): boolean {
  return localStorage.getItem(MEDIA_DUCKING_STORAGE_KEY) !== "false";
}

export function setMediaDuckingEnabled(enabled: boolean): void {
  localStorage.setItem(MEDIA_DUCKING_STORAGE_KEY, String(enabled));
  window.dispatchEvent(new Event(CHANGE_EVENT));
  if (!enabled && isTauriRuntime()) void dispatchDucking("idle", getMediaDuckingLevel());
}

export function getMediaDuckingLevel(): number {
  const value = Number(localStorage.getItem(MEDIA_DUCKING_LEVEL_STORAGE_KEY));
  return Number.isFinite(value) && value >= 0.10 && value <= 1
    ? value
    : DEFAULT_MEDIA_DUCKING_LEVEL;
}

export function setMediaDuckingLevel(level: number): void {
  const bounded = Math.min(1, Math.max(0.10, level));
  localStorage.setItem(MEDIA_DUCKING_LEVEL_STORAGE_KEY, String(bounded));
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

export function subscribeMediaDucking(listener: () => void): () => void {
  window.addEventListener(CHANGE_EVENT, listener);
  return () => window.removeEventListener(CHANGE_EVENT, listener);
}

export function useMediaDuckingEnabled(): boolean {
  return useSyncExternalStore(subscribeMediaDucking, getMediaDuckingEnabled, () => true);
}

export function useMediaDuckingLevel(): number {
  return useSyncExternalStore(subscribeMediaDucking, getMediaDuckingLevel, () => DEFAULT_MEDIA_DUCKING_LEVEL);
}

export function mapVoiceToDuckingState(state: PipelineState): MediaDuckingState {
  return state === "conversing" ? "processing" : state;
}

export function createDuckingDispatcher(
  send: (state: MediaDuckingState, volumeFactor: number) => Promise<unknown>,
) {
  let requested: string | null = null;
  let queue = Promise.resolve();
  return (state: MediaDuckingState, volumeFactor: number) => {
    const key = `${state}:${volumeFactor}`;
    if (key === requested) return queue;
    requested = key;
    queue = queue.then(async () => {
      try {
        await send(state, volumeFactor);
      } catch {
        if (requested === key) requested = null;
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
  const volumeFactor = useMediaDuckingLevel();

  useEffect(() => {
    if (!isTauriRuntime()) return;
    void dispatchDucking(enabled ? mapVoiceToDuckingState(voice.state) : "idle", volumeFactor);
  }, [enabled, voice.state, volumeFactor]);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    const restore = () => void dispatchDucking("idle", getMediaDuckingLevel());
    window.addEventListener("pagehide", restore);
    return () => {
      window.removeEventListener("pagehide", restore);
      restore();
    };
  }, []);

  return null;
}
