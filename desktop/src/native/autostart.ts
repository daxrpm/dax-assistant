import { invoke } from "@tauri-apps/api/core";
import { isTauriRuntime } from "./environment";

export type AutostartState =
  | { available: true; enabled: boolean }
  | { available: false; enabled: false; reason: string };

const unavailable = (): AutostartState => ({
  available: false,
  enabled: false,
  reason: "Autostart is only available in the installed desktop app.",
});

export async function getAutostart(): Promise<AutostartState> {
  if (!isTauriRuntime()) return unavailable();
  return {
    available: true,
    enabled: await invoke<boolean>("plugin:autostart|is_enabled"),
  };
}

export async function setAutostart(enabled: boolean): Promise<AutostartState> {
  if (!isTauriRuntime()) return unavailable();
  await invoke(`plugin:autostart|${enabled ? "enable" : "disable"}`);
  return getAutostart();
}
