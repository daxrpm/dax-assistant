/**
 * HTTP client — ported from `web/src/api/client.ts`.
 *
 * Two differences from the web version, both required by PLAN.md 3.1/3.5:
 *   1. The base URL is an absolute origin, not `/api`, because the webview is
 *      served from a custom protocol rather than by FastAPI.
 *   2. Auth is `Authorization: Bearer <token>` rather than a cookie, because a
 *      SameSite=lax cookie is not reliably replayed cross-origin from a
 *      webview. The cookie is still sent when present; the backend accepts
 *      whichever credential validates.
 */

import { currentToken, getBaseUrl } from "./connection";
import type {
  AuthStatus,
  ConversationDetail,
  ConversationSummary,
  FullConfig,
  HealthResponse,
  LoginResponse,
  LogEntry,
  MCPAuthStatus,
  MCPPreset,
  MCPServerConfig,
  MCPServerStatus,
  MemoryEntry,
  OllamaModel,
  RegistrySearchResponse,
  ShellAllowResponse,
  StatusResponse,
  ToolAuditEntry,
  ToolPolicyResponse,
  VoiceProfileResponse,
  VoicePreviewOptions,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "ApiError";
    this.status = status;
  }

  /** Status 0 means the request never reached the backend. */
  get isUnreachable(): boolean {
    return this.status === 0;
  }
}

function authHeaders(): Record<string, string> {
  const token = currentToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function responseError(response: Response): Promise<never> {
  const text = await response.text();
  let message = text;
  try {
    const body = JSON.parse(text) as { detail?: string };
    message = body.detail ?? text;
  } catch {
    // Preserve non-JSON server errors verbatim.
  }
  throw new ApiError(response.status, message || `API error ${response.status}`);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}/api${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...authHeaders(),
        ...(options?.headers ?? {}),
      },
      credentials: "include",
    });
  } catch (cause) {
    // fetch() rejects on DNS/connection failure — surface it as a 0 so callers
    // can distinguish "backend is down" from "backend said no".
    throw new ApiError(0, `Cannot reach backend at ${getBaseUrl()}`, { cause });
  }
  if (!response.ok) return responseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/**
 * POST returning a binary body (`/api/voice/preview` → audio/wav).
 * Cannot go through `request()` because that always parses JSON.
 */
async function requestBlob(path: string, body: Record<string, unknown>): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}/api${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      credentials: "include",
      body: JSON.stringify(body),
    });
  } catch (cause) {
    throw new ApiError(0, `Cannot reach backend at ${getBaseUrl()}`, { cause });
  }
  if (!response.ok) return responseError(response);
  return response.blob();
}

/**
 * multipart/form-data POST. Deliberately does NOT set Content-Type — the
 * browser must add the multipart boundary itself.
 */
async function requestForm<T>(path: string, form: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${getBaseUrl()}/api${path}`, {
      method: "POST",
      headers: authHeaders(),
      credentials: "include",
      body: form,
    });
  } catch (cause) {
    throw new ApiError(0, `Cannot reach backend at ${getBaseUrl()}`, { cause });
  }
  if (!response.ok) return responseError(response);
  return (await response.json()) as T;
}

/* ---------------- auth ---------------- */

export const api = {
  health: () => request<HealthResponse>("/health"),

  authStatus: () => request<AuthStatus>("/auth/status"),

  login: (password: string) =>
    request<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  setup: (password: string) =>
    request<LoginResponse>("/auth/setup", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  logout: () => request<LoginResponse>("/auth/logout", { method: "POST" }),

  /* ---------------- status / dashboard ---------------- */

  status: () => request<StatusResponse>("/status"),

  mcpStatus: () => request<MCPServerStatus[]>("/mcp/status"),

  logs: (limit = 200) => request<LogEntry[]>(`/logs?limit=${limit}`),

  toolAudit: (limit = 50) => request<ToolAuditEntry[]>(`/tools/audit?limit=${limit}`),

  toolPolicy: () => request<ToolPolicyResponse>("/tools/policy"),

  ollamaModels: () => request<OllamaModel[]>("/ollama/models"),

  /** `provider` omitted lists every provider's models, keyed by provider. */
  llmModels: (provider?: string) =>
    request<Record<string, string[]>>(
      `/llm/models${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`,
    ),

  toggleVoice: (enabled: boolean) =>
    request<{ voice_listening: boolean }>("/voice/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),

  pushToTalkPress: () =>
    request<{ status: string; state: string }>("/voice/push-to-talk/press", {
      method: "POST",
    }),

  pushToTalkRelease: () =>
    request<{ status: string; state: string }>("/voice/push-to-talk/release", {
      method: "POST",
    }),

  /* ---------------- conversations ---------------- */

  conversations: (limit = 50) =>
    request<ConversationSummary[]>(`/conversations?limit=${limit}`),

  conversation: (id: string) => request<ConversationDetail>(`/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: "DELETE" }),

  /* ---------------- config ---------------- */

  config: () => request<FullConfig>("/config"),

  updateGeneral: (data: Record<string, unknown>) =>
    request<unknown>("/config/general", { method: "PATCH", body: JSON.stringify(data) }),

  resetSystemPrompt: () =>
    request<{ status: string; system_prompt: string }>(
      "/config/general/system-prompt/reset",
      { method: "POST" },
    ),

  updateLLM: (data: Record<string, unknown>) =>
    request<unknown>("/config/llm", { method: "PATCH", body: JSON.stringify(data) }),

  updateVoice: (data: Record<string, unknown>) =>
    request<unknown>("/config/voice", { method: "PATCH", body: JSON.stringify(data) }),

  updateTools: (data: Record<string, unknown>) =>
    request<unknown>("/config/tools", { method: "PATCH", body: JSON.stringify(data) }),

  updateSecurity: (data: Record<string, unknown>) =>
    request<unknown>("/config/security", { method: "PATCH", body: JSON.stringify(data) }),

  updateWeb: (data: Record<string, unknown>) =>
    request<unknown>("/config/web", { method: "PATCH", body: JSON.stringify(data) }),

  updateTelegram: (data: Record<string, unknown>) =>
    request<unknown>("/config/telegram", { method: "PATCH", body: JSON.stringify(data) }),

  updateWhatsApp: (data: Record<string, unknown>) =>
    request<unknown>("/config/whatsapp", { method: "PATCH", body: JSON.stringify(data) }),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ status: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    }),

  /* ---------------- MCP servers ---------------- */

  mcpServers: () => request<Record<string, MCPServerConfig>>("/config/mcp/servers"),

  addMcpServer: (data: Record<string, unknown>) =>
    request<unknown>("/config/mcp/servers", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateMcpServer: (name: string, data: Record<string, unknown>) =>
    request<unknown>(`/config/mcp/servers/${encodeURIComponent(name)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteMcpServer: (name: string) =>
    request<void>(`/config/mcp/servers/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  reconnectMcpServer: (name: string) =>
    request<{ status: string; tools: number }>(
      `/config/mcp/servers/${encodeURIComponent(name)}/reconnect`,
      { method: "POST" },
    ),

  /* ---------------- dax-system shell allowlist ---------------- */

  shellAllow: () => request<ShellAllowResponse>("/config/system/shell-allow"),

  updateShellAllow: (commands: string[]) =>
    request<{ status: string; commands: string[] }>("/config/system/shell-allow", {
      method: "PUT",
      body: JSON.stringify({ commands }),
    }),

  /* ---------------- MCP export + marketplace ---------------- */

  codexConfig: () =>
    request<{ toml: string; server_count: number; note: string }>("/codex-config"),

  claudeConfig: () =>
    request<{ json: string; server_count: number; note: string }>("/claude-config"),

  mcpPresets: () => request<MCPPreset[]>("/mcp/presets"),

  searchMcpRegistry: (q: string, limit = 30) =>
    request<RegistrySearchResponse>(
      `/mcp/registry/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  /* ---------------- MCP OAuth ---------------- */

  startMcpAuth: (name: string) =>
    request<{ authorization_url: string; state: string }>(
      `/mcp/${encodeURIComponent(name)}/auth/start`,
      { method: "POST" },
    ),

  mcpAuthStatus: (name: string) =>
    request<MCPAuthStatus>(`/mcp/${encodeURIComponent(name)}/auth/status`),

  logoutMcp: (name: string) =>
    request<unknown>(`/mcp/${encodeURIComponent(name)}/auth/logout`, { method: "POST" }),

  /* ---------------- memory ---------------- */

  listMemory: () => request<MemoryEntry[]>("/memory"),

  getMemory: (slug: string) => request<MemoryEntry>(`/memory/${encodeURIComponent(slug)}`),

  createMemory: (data: {
    name: string;
    body: string;
    description?: string;
    type?: string;
  }) => request<MemoryEntry>("/memory", { method: "POST", body: JSON.stringify(data) }),

  updateMemory: (
    slug: string,
    data: { name?: string; body?: string; description?: string; type?: string },
  ) =>
    request<{ status: string }>(`/memory/${encodeURIComponent(slug)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteMemory: (slug: string) =>
    request<void>(`/memory/${encodeURIComponent(slug)}`, { method: "DELETE" }),

  /* ---------------- voice ---------------- */

  voiceProfile: () => request<VoiceProfileResponse>("/voice/profile"),

  enrollVoice: (samples: Blob[]) => {
    const form = new FormData();
    samples.forEach((sample, i) => form.append("samples", sample, `voice-${i + 1}.wav`));
    return requestForm<VoiceProfileResponse>("/voice/enroll", form);
  },

  deleteVoiceProfile: () =>
    request<VoiceProfileResponse>("/voice/profile", { method: "DELETE" }),

  previewVoice: (options: VoicePreviewOptions) =>
    requestBlob("/voice/preview", options as unknown as Record<string, unknown>),
};
