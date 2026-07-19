import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export type MediaAction = "previous" | "play_pause" | "next";
export type MediaDuckingState = "idle" | "listening" | "processing" | "speaking";

export interface MediaSnapshot {
  available: boolean;
  player: string | null;
  identity: string | null;
  status: string | null;
  title: string | null;
  artist: string | null;
  album: string | null;
  position_seconds: number | null;
  duration_seconds: number | null;
}

export interface MediaSpectrumFrame {
  bands: number[];
  bass: number;
  level: number;
}

export function getMediaStatus(): Promise<MediaSnapshot> {
  return invoke<MediaSnapshot>("media_status");
}

export function controlMedia(action: MediaAction): Promise<void> {
  return invoke<void>("media_control", { action });
}

export function setMediaDucking(duckingState: MediaDuckingState): Promise<void> {
  return invoke<void>("media_set_ducking", { duckingState });
}

export function startMediaSpectrum(): Promise<void> {
  return invoke<void>("media_spectrum_start");
}

export function stopMediaSpectrum(): Promise<void> {
  return invoke<void>("media_spectrum_stop");
}

export function listenMediaSpectrum(
  onFrame: (frame: MediaSpectrumFrame) => void,
): Promise<UnlistenFn> {
  return listen<MediaSpectrumFrame>("media://spectrum", (event) => onFrame(event.payload));
}
