/**
 * Where the backend is, and how we authenticate to it.
 *
 * Default mode is "remote" pointed at the already-running backend
 * (PLAN.md 3.7 option C) — the desktop app is useful without solving Python
 * packaging at all.
 *
 * The token lives in the OS keyring via Rust (`session_token_get/set/clear`),
 * NOT in localStorage. `localStorage` is only used for the base URL, which is
 * not a secret.
 */

import { invoke } from "@tauri-apps/api/core";

export const DEFAULT_BASE_URL = "http://127.0.0.1:8420";

const BASE_URL_KEY = "dax.backend.baseUrl";

/** True when running inside the Tauri webview rather than a plain browser. */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export function getBaseUrl(): string {
  const stored = localStorage.getItem(BASE_URL_KEY);
  if (stored && stored.trim()) return stored.replace(/\/+$/, "");
  // In a plain browser (`npm run dev` without Tauri) go same-origin and let
  // the Vite proxy reach the backend. An absolute URL here would be a
  // cross-origin request from a dev port the backend does not allow, which
  // surfaces as "Backend unreachable" against a perfectly healthy backend.
  if (!isTauri()) return "";
  return DEFAULT_BASE_URL;
}

export function setBaseUrl(url: string): void {
  localStorage.setItem(BASE_URL_KEY, url.replace(/\/+$/, ""));
}

/** Derive the ws:// or wss:// origin for the WebSocket endpoints. */
export function getWsUrl(path: string, token: string | null): string {
  const configured = getBaseUrl();
  // Same-origin (browser dev) has no base to derive from, so build the ws
  // origin off the page itself.
  const base = configured
    ? configured.replace(/^http/, "ws")
    : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
  // WebSocket handshakes can't carry an Authorization header from the browser
  // API, so the backend also accepts `?token=` (src/dax/web/auth.py).
  const query = token ? `?token=${encodeURIComponent(token)}` : "";
  return `${base}${path}${query}`;
}

/*
 * Token storage. Inside Tauri this round-trips through the OS keyring.
 * In a plain browser (`npm run dev` without Tauri) it falls back to
 * sessionStorage so the UI is still developable.
 */

const FALLBACK_TOKEN_KEY = "dax.session.token";

let cachedToken: string | null = null;

export async function loadToken(): Promise<string | null> {
  if (isTauri()) {
    try {
      cachedToken = await invoke<string | null>("session_token_get");
    } catch {
      cachedToken = null;
    }
  } else {
    cachedToken = sessionStorage.getItem(FALLBACK_TOKEN_KEY);
  }
  return cachedToken;
}

export async function storeToken(token: string): Promise<void> {
  cachedToken = token;
  if (isTauri()) {
    await invoke("session_token_set", { token });
  } else {
    sessionStorage.setItem(FALLBACK_TOKEN_KEY, token);
  }
}

export async function clearToken(): Promise<void> {
  cachedToken = null;
  if (isTauri()) {
    await invoke("session_token_clear");
  } else {
    sessionStorage.removeItem(FALLBACK_TOKEN_KEY);
  }
}

/** Synchronous read of the last loaded token, for request headers. */
export function currentToken(): string | null {
  return cachedToken;
}
