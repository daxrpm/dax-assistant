/** Backend selection and origin-scoped authentication. */

import { invoke } from "@tauri-apps/api/core";
import {
  getNativeBackendSettings,
  replaceNativeAuthorityConfirmed,
  resolveNativeBackend,
  saveNativeBackendSettings,
  type BackendResolution,
  type BackendSettings,
  type BackendSettingsInput,
  type BackendStrategy,
} from "../native/backend";
import { isTauriRuntime } from "../native/environment";
import type { HealthResponse } from "./types";

export const DEFAULT_BASE_URL = "http://127.0.0.1:8420";
const SETTINGS_KEY = "dax.backend.settings.v3";
const VERSION_TWO_SETTINGS_KEY = "dax.backend.settings.v2";
const LEGACY_BASE_URL_KEY = "dax.backend.baseUrl";
const FALLBACK_TOKEN_PREFIX = "dax.session.token.v3:";
const ORIGIN_ONLY_TOKEN_PREFIX = "dax.session.token:";

let configuredBaseUrl = DEFAULT_BASE_URL;
let cachedSettings: BackendSettings | null = null;
let cachedToken: string | null = null;
let tokenLoadGeneration = 0;
let configuredServerInstanceId: string | null = null;
let authorityValidated = false;

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
  if (!/^\/+$/u.test(parsed.pathname)) {
    throw new Error("Backend URL must not contain a path");
  }
  return parsed.toString().replace(/\/+$/, "");
}

export function connectionCandidates(
  strategy: BackendStrategy,
  localUrl: string,
  remoteUrl: string | null,
): string[] {
  if (strategy === "local") return [localUrl];
  return remoteUrl ? [remoteUrl] : [];
}

export function authoritativeHealthIdentity(health: HealthResponse): string | null {
  return health.status === "ok"
    && health.role === "authoritative"
    && health.api_protocol === "dax"
    && health.api_version === 1
    && health.liveness === true
    && health.readiness === true
    && typeof health.instance_id === "string"
    && health.instance_id.length > 0
    ? health.instance_id
    : null;
}

export function validateCurrentAuthorityHealth(health: HealthResponse): string {
  const identity = authoritativeHealthIdentity(health);
  if (!identity) throw new Error("The endpoint is not a ready authoritative Dax backend");
  if (configuredServerInstanceId && identity !== configuredServerInstanceId) {
    throw new Error("Backend authority identity changed; reconnect explicitly");
  }
  return identity;
}

async function probeAuthoritativeBackend(url: string): Promise<string | null> {
  try {
    const response = await fetch(`${url}/api/health`, {
      signal: AbortSignal.timeout(2_000),
    });
    if (!response.ok) return null;
    return authoritativeHealthIdentity(await response.json() as HealthResponse);
  } catch {
    return null;
  }
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
    active_server_id: null,
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
    if (stored) {
      cachedSettings = JSON.parse(stored) as BackendSettings;
    } else {
      const versionTwo = localStorage.getItem(VERSION_TWO_SETTINGS_KEY);
      if (versionTwo) {
        const old = JSON.parse(versionTwo) as Omit<BackendSettings, "active_server_id"> & {
          strategy: BackendStrategy | "hybrid";
        };
        const strategy: BackendStrategy = old.strategy === "local" ? "local" : "remote";
        const activeUrl = strategy === "local" ? old.local_url : old.remote_url;
        if (!activeUrl) throw new Error("Version 2 server settings require a remote URL");
        cachedSettings = {
          ...old,
          version: 3,
          strategy,
          active_url: activeUrl,
          active_server_id: null,
        };
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(cachedSettings));
        localStorage.removeItem(VERSION_TWO_SETTINGS_KEY);
      } else {
        cachedSettings = browserDefaults();
      }
    }
  }
  configuredBaseUrl = cachedSettings.active_url;
  configuredServerInstanceId = cachedSettings.active_server_id;
  authorityValidated = false;
  cachedToken = null;
  tokenLoadGeneration += 1;
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
  const nextUrl = input.strategy === "local" ? localUrl : remoteUrl!;
  const authorityChanged = tokenOrigin(nextUrl) !== tokenOrigin(configuredBaseUrl);
  if (authorityChanged) await discardActiveCredential();
  authorityValidated = false;
  cachedToken = null;
  tokenLoadGeneration += 1;
  if (isTauri()) {
    cachedSettings = await saveNativeBackendSettings({
      ...input,
      localUrl,
      remoteUrl,
    });
  } else {
    cachedSettings = {
      version: 3,
      strategy: input.strategy,
      local_url: localUrl,
      remote_url: remoteUrl,
      active_url: nextUrl,
      active_server_id: authorityChanged ? null : configuredServerInstanceId,
      onboarding_complete: input.onboardingComplete,
    };
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(cachedSettings));
  }
  configuredBaseUrl = cachedSettings.active_url;
  configuredServerInstanceId = cachedSettings.active_server_id;
  return cachedSettings;
}

export async function resolveConnection(
  allowServiceStart: boolean,
  beforeOriginSwitch: () => void | Promise<void>,
): Promise<BackendResolution> {
  if (!cachedSettings) await loadConnectionSettings();
  if (!isTauri()) {
    const serverInstanceId = await probeAuthoritativeBackend(cachedSettings!.active_url);
    const healthy = serverInstanceId !== null;
    if (configuredServerInstanceId && serverInstanceId !== configuredServerInstanceId) {
      await discardActiveCredential();
      throw new Error("Backend authority identity changed; reconnect explicitly");
    }
    if (serverInstanceId) {
      configuredServerInstanceId = serverInstanceId;
      authorityValidated = true;
      cachedSettings = { ...cachedSettings!, active_server_id: serverInstanceId };
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(cachedSettings));
      await loadToken();
    } else {
      invalidateLoadedToken();
    }
    return {
      strategy: cachedSettings!.strategy,
      active_url: cachedSettings!.active_url,
      previous_url: configuredBaseUrl,
      changed: false,
      healthy,
      server_instance_id: serverInstanceId,
      service_start_attempted: false,
      attempts: [],
    };
  }
  const result = await resolveNativeBackend(allowServiceStart);
  const observedIdentity = result.attempts.find(
    (attempt) => tokenOrigin(attempt.url) === tokenOrigin(configuredBaseUrl),
  )?.server_instance_id ?? result.server_instance_id;
  if (configuredServerInstanceId && observedIdentity && observedIdentity !== configuredServerInstanceId) {
    await discardActiveCredential();
    throw new Error("Backend authority identity changed; reconnect explicitly");
  }
  if (result.active_url !== configuredBaseUrl) {
    await beforeOriginSwitch();
    cachedToken = null;
    tokenLoadGeneration += 1;
  }
  configuredBaseUrl = result.active_url;
  if (!result.healthy || !result.server_instance_id) {
    invalidateLoadedToken();
    return result;
  }
  configuredServerInstanceId = result.server_instance_id;
  authorityValidated = true;
  cachedSettings = {
    ...cachedSettings!,
    active_url: result.active_url,
    active_server_id: result.server_instance_id,
  };
  await loadToken();
  return result;
}

export async function recoverSameOriginAuthorityReplacement(): Promise<BackendResolution> {
  if (!isTauri()) throw new Error("Authority replacement recovery requires Dax Desktop");

  cachedSettings = await replaceNativeAuthorityConfirmed();
  configuredBaseUrl = cachedSettings.active_url;
  configuredServerInstanceId = null;
  invalidateLoadedToken();

  const result = await resolveNativeBackend(false);
  if (!result.healthy || !result.server_instance_id) return result;

  configuredBaseUrl = result.active_url;
  configuredServerInstanceId = result.server_instance_id;
  authorityValidated = true;
  cachedSettings = {
    ...cachedSettings,
    active_url: result.active_url,
    active_server_id: result.server_instance_id,
  };
  // Recovery always returns to login, even if this replacement was seen before.
  await clearToken();
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
  if (!configuredServerInstanceId) throw new Error("Backend authority identity is not pinned");
  return `${FALLBACK_TOKEN_PREFIX}${encodeURIComponent(tokenOrigin(value))}:${encodeURIComponent(configuredServerInstanceId)}`;
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
  if (!authorityValidated || !configuredServerInstanceId) {
    invalidateLoadedToken();
    return null;
  }
  const origin = tokenOrigin();
  const instanceId = configuredServerInstanceId;
  const generation = ++tokenLoadGeneration;
  let token: string | null;
  if (isTauri()) {
    try {
      token = await invoke<string | null>("session_token_get", { origin, instanceId });
    } catch {
      token = null;
    }
  } else {
    sessionStorage.removeItem(`${ORIGIN_ONLY_TOKEN_PREFIX}${encodeURIComponent(origin)}`);
    token = sessionStorage.getItem(tokenStorageKey());
  }
  if (generation !== tokenLoadGeneration || origin !== tokenOrigin()
    || instanceId !== configuredServerInstanceId || !authorityValidated) return null;
  cachedToken = token;
  return token;
}

export async function storeToken(token: string): Promise<void> {
  if (!authorityValidated || !configuredServerInstanceId) {
    throw new Error("Backend authority must be validated before storing credentials");
  }
  tokenLoadGeneration += 1;
  const origin = tokenOrigin();
  if (isTauri()) {
    await invoke("session_token_set", { origin, instanceId: configuredServerInstanceId, token });
  } else {
    sessionStorage.setItem(tokenStorageKey(), token);
  }
  cachedToken = token;
}

export async function clearToken(): Promise<void> {
  tokenLoadGeneration += 1;
  const origin = tokenOrigin();
  if (isTauri() && configuredServerInstanceId) {
    await invoke("session_token_clear", { origin, instanceId: configuredServerInstanceId });
  } else {
    if (configuredServerInstanceId) sessionStorage.removeItem(tokenStorageKey());
  }
  cachedToken = null;
}

export function currentToken(): string | null {
  return authorityValidated ? cachedToken : null;
}

function invalidateLoadedToken(): void {
  authorityValidated = false;
  cachedToken = null;
  tokenLoadGeneration += 1;
}

async function discardActiveCredential(): Promise<void> {
  invalidateLoadedToken();
  if (!configuredServerInstanceId) return;
  const origin = tokenOrigin();
  if (isTauri()) {
    await invoke("session_token_clear", { origin, instanceId: configuredServerInstanceId });
  } else {
    sessionStorage.removeItem(tokenStorageKey());
  }
}
