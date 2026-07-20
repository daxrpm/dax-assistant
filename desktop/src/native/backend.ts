import { invoke } from "@tauri-apps/api/core";

export type BackendStrategy = "local" | "remote";

export interface BackendSettings {
  version: number;
  strategy: BackendStrategy;
  local_url: string;
  remote_url: string | null;
  active_url: string;
  active_server_id: string | null;
  onboarding_complete: boolean;
}

export interface BackendResolution {
  strategy: BackendStrategy;
  active_url: string;
  previous_url: string;
  changed: boolean;
  healthy: boolean;
  server_instance_id: string | null;
  service_start_attempted: boolean;
  attempts: Array<{ url: string; healthy: boolean; server_instance_id: string | null }>;
}

export interface BackendSettingsInput {
  strategy: BackendStrategy;
  localUrl: string;
  remoteUrl?: string | null;
  onboardingComplete: boolean;
}

export function getNativeBackendSettings(): Promise<BackendSettings> {
  return invoke<BackendSettings>("backend_settings_get");
}

export function saveNativeBackendSettings(
  input: BackendSettingsInput,
): Promise<BackendSettings> {
  return invoke<BackendSettings>("backend_settings_set", { ...input });
}

export function resolveNativeBackend(
  allowServiceStart = false,
): Promise<BackendResolution> {
  return invoke<BackendResolution>("backend_resolve", { allowServiceStart });
}

export function replaceNativeAuthorityConfirmed(): Promise<BackendSettings> {
  return invoke<BackendSettings>("backend_authority_replace_confirmed");
}
