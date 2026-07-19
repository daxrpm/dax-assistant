import { invoke } from "@tauri-apps/api/core";

export function showVoiceHud(): Promise<void> {
  return invoke("voice_hud_show");
}

export function hideVoiceHud(): Promise<void> {
  return invoke("voice_hud_hide");
}

export function toggleVoiceHud(): Promise<boolean> {
  return invoke<boolean>("voice_hud_toggle");
}
