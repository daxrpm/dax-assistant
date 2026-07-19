/** Backend selection and origin-scoped authentication. */

import { invoke } from "@tauri-apps/api/core";
import {
  getNativeBackendSettings,
  resolveNativeBackend,
  saveNativeBackendSettings,
  type BackendResolution,
  type BackendSettings,
  type BackendSettingsInput,
  type BackendStrategy,
} from "../native/backend";
import { isTauriRuntime } from "../native/environment";

export const DEFAULT_BASE_URL = "http://127.0.0.1:8420";
const SETTINGS_KEY = "dax.backend.settings.v2";
const LEGACY_BASE_URL_KEY = "dax.backend.baseUrl";
const FALLBACK_TOKEN_PREFIX = "dax.session.token:";

let configuredBaseUrl = DEFAULT_BASE_URL;
let cachedSettings: BackendSettings | null = null;
let cachedToken: string | null = null;

export function isTauri(): boolean {
  return isTauriRuntime();
}

export function validateBaseUrl(value: string, requireLoopback = false): string {
  const trimmed = value.trim();
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error("Invalid backend URL");
  }
  if (parsed.username || parsed.password) {
    throw new Error("Backend URL must not contain credentials");
  }
  if (parsed.search || parsed.hash) {
    throw new Error("Backend URL must not contain a query or fragment");
  }
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(
    parsed.hostname.toLowerCase(),
  );
  if (requireLoopback && !loopback) {
    throw new Error("Local backend URL must use a loopback host");
  }
  if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && loopback)) {
    throw new Error("Remote backend URLs must use HTTPS");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("Backend URL scheme must be HTTP or HTTPS");
  }
  return parsed.toString().replace(/\/+$/, "");
}

export function connectionCandidates(
  strategy: BackendStrategy,
  localUrl: string,
  remoteUrl: string | null,
): string[] {
  if (strategy === "local") return [localUrl];
  if (strategy === "remote") return remoteUrl ? [remoteUrl] : [];
  return remoteUrl ? [remoteUrl, localUrl] : [localUrl];
}

function browserDefaults(): BackendSettings {
  const legacy = localStorage.getItem(LEGACY_BASE_URL_KEY);
  const active = legacy?.trim() ? validateBaseUrl(legacy) : DEFAULT_BASE_URL;
  return {
    version: 2,
    strategy: isLoopbackUrl(active) ? "local" : "remote",
    local_url: DEFAULT_BASE_URL,
    remote_url: isLoopbackUrl(active) ? null : active,
    active_url: active,
    // Browser mode is a development fallback and has no native service setup.
    onboarding_complete: true,
  };
}

/** Loads settings only. Network resolution is always a separate explicit step. */
export async function loadConnectionSettings(): Promise<BackendSettings> {
  if (isTauri()) {
    cachedSettings = await getNativeBackendSettings();
  } else {
    const stored = localStorage.getItem(SETTINGS_KEY);
    cachedSettings = stored ? (JSON.parse(stored) as BackendSettings) : browserDefaults();
  }
  configuredBaseUrl = cachedSettings.active_url;
  return cachedSettings;
}

export function getConnectionSettings(): BackendSettings | null {
  return cachedSettings;
}

export async function saveConnectionSettings(
  input: BackendSettingsInput,
): Promise<BackendSettings> {
  const localUrl = validateBaseUrl(input.localUrl, true);
  const remoteUrl = input.remoteUrl?.trim()
    ? validateBaseUrl(input.remoteUrl)
    : null;
  if (input.strategy !== "local" && !remoteUrl) {
    throw new Error("A remote URL is required for this strategy");
  }
  if (isTauri()) {
    cachedSettings = await saveNativeBackendSettings({
      ...input,
      localUrl,
      remoteUrl,
    });
  } else {
    const active = input.strategy === "local" ? localUrl : remoteUrl!;
    cachedSettings = {
      version: 2,
      strategy: input.strategy,
      local_url: localUrl,
      remote_url: remoteUrl,
      active_url: active,
      onboarding_complete: input.onboardingComplete,
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(cachedSettings));
  }
  configuredBaseUrl = cachedSettings.active_url;
  return cachedSettings;
}

export async function resolveConnection(
  allowServiceStart = false,
): Promise<BackendResolution> {
  if (!cachedSettings) await loadConnectionSettings();
  if (!isTauri()) {
    return {
      strategy: cachedSettings!.strategy,
      active_url: cachedSettings!.active_url,
      previous_url: configuredBaseUrl,
      changed: false,
      healthy: true,
      service_start_attempted: false,
      attempts: [],
    };
  }
  const result = await resolveNativeBackend(allowServiceStart);
  configuredBaseUrl = result.active_url;
  cachedSettings = { ...cachedSettings!, active_url: result.active_url };
  return result;
}

export function getBaseUrl(): string {
  return configuredBaseUrl;
}

export function isLoopbackUrl(value = configuredBaseUrl): boolean {
  if (!value) return true;
  const hostname = new URL(value).hostname.toLowerCase();
  return ["localhost", "127.0.0.1", "[::1]"].includes(hostname);
}

export function usesRemoteAudio(): boolean {
  return !isLoopbackUrl();
}

export function tokenOrigin(value = configuredBaseUrl): string {
  return new URL(value).origin;
}

export function tokenStorageKey(value = configuredBaseUrl): string {
  return `${FALLBACK_TOKEN_PREFIX}${encodeURIComponent(tokenOrigin(value))}`;
}

export function getWsUrl(path: string, token: string | null): string {
  const configured = getBaseUrl();
  const base = configured
    ? configured.replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  const result = `${base}${path}${query}`;
  const parsed = new URL(result);
  if (!isLoopbackUrl(parsed.toString()) && parsed.protocol !== "wss:") {
    throw new Error("Remote WebSocket connections must use WSS");
  }
  return result;
}

export async function loadToken(): Promise<string | null> {
  const origin = tokenOrigin();
  if (isTauri()) {
    try {
      cachedToken = await invoke<string | null>("session_token_get", { origin });
    } catch {
      cachedToken = null;
    }
  } else {
    cachedToken = sessionStorage.getItem(tokenStorageKey());
  }
  return cachedToken;
}

export async function storeToken(token: string): Promise<void> {
  cachedToken = token;
  const origin = tokenOrigin();
  if (isTauri()) {
    await invoke("session_token_set", { origin, token });
  } else {
    sessionStorage.setItem(tokenStorageKey(), token);
  }
}

export async function clearToken(): Promise<void> {
  cachedToken = null;
  const origin = tokenOrigin();
  if (isTauri()) {
    await invoke("session_token_clear", { origin });
  } else {
    sessionStorage.removeItem(tokenStorageKey());
  }
}

export function currentToken(): string | null {
  return cachedToken;
}
