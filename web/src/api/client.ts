import type { FullConfig, LogEntry, StatusResponse } from "../types/config";

const BASE = "/api";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin", // send the session cookie
    ...options,
  });
  if (!response.ok) {
    return responseError(response);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

async function responseError(response: Response): Promise<never> {
  const text = await response.text();
  let message = text;
  try {
    const body = JSON.parse(text) as { detail?: string };
    message = body.detail ?? text;
  } catch {
    // Preserve non-JSON server errors.
  }
  throw new ApiError(response.status, message || `API error ${response.status}`);
}

async function requestBlob(path: string, body: Record<string, unknown>): Promise<Blob> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  if (!response.ok) return responseError(response);
  return response.blob();
}

export interface AuthStatus {
  auth_enabled: boolean;
  configured: boolean;
  authenticated: boolean;
}

export interface ToolAuditEntry {
  timestamp: string;
  server_name: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: string;
}

export interface ConversationSummary {
  id: string;
  session_key: string;
  title: string;
  preview: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationMessage {
  id: string;
  role: string;
  content: string;
  timestamp: string;
}

export interface ConversationDetail {
  id: string;
  session_key: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

export interface MemoryEntry {
  slug: string;
  name: string;
  description: string;
  type: "user" | "feedback" | "project" | "reference";
  body: string;
  filename: string;
}

export interface MCPPreset {
  id: string;
  name: string;
  category: string;
  description: string;
  transport: string;
  command: string;
  args: string[];
  env: Record<string, string>;
}

export interface RegistryServer {
  name: string;
  description: string;
  version: string;
  packages: { registry_type: string; identifier: string; version: string }[];
  remotes: { type: string; url: string }[];
}

export interface MCPServerStatus {
  name: string;
  connected: boolean;
  transport: string;
  enabled: boolean;
  tool_count: number;
  tools: string[];
}

export interface PairCodeResponse {
  code: string;
  expires_in_seconds: number;
  backend_url: string;
  pairing_uri: string;
  kind: DeviceKind;
}

export type DeviceKind = "client" | "capability_node";

export interface PairedDevice {
  id: string;
  name: string;
  platform: string;
  created_at: string;
  last_seen_at: string | null;
  revoked_at: string | null;
  revoked: boolean;
  connected: boolean;
  kind: DeviceKind;
}

export interface ToolPolicyResponse {
  default: string;
  allow: string[];
  ask: string[];
  deny: string[];
  confirm_timeout_seconds: number;
}

export interface ShellAllowResponse {
  commands: string[];
  default: string[];
}

export interface VoiceProfileResponse {
  status?: string;
  enrolled: boolean;
  samples?: number;
}

export interface VoicePreviewOptions {
  engine: "kokoro" | "piper" | "openai";
  voice: string;
  language?: "es" | "en";
  text?: string;
  speed?: number;
  model?: string;
  instructions?: string;
  timeout_s?: number;
}

interface OllamaModel {
  name: string;
  size_gb: number;
  modified: string;
  family: string;
  parameters: string;
  quantization: string;
}

export const api = {
  // Auth
  authStatus: () => request<AuthStatus>("/auth/status"),

  login: (password: string) =>
    request<{ ok: boolean; detail?: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  setup: (password: string) =>
    request<{ ok: boolean; detail?: string }>("/auth/setup", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),

  pairDevice: (kind: DeviceKind = "client") =>
    request<PairCodeResponse>("/auth/devices/pair", {
      method: "POST",
      ...(kind === "client"
        ? {}
        : { body: JSON.stringify({ kind, backend_url: window.location.origin }) }),
    }),

  devices: () => request<{ devices: PairedDevice[] }>("/auth/devices"),

  revokeDevice: (id: string) =>
    request<{ ok: boolean }>(`/auth/devices/${encodeURIComponent(id)}/revoke`, {
      method: "POST",
    }),

  deleteDevice: (id: string) =>
    request<{ ok: boolean }>(`/auth/devices/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),

  // Tools
  getToolAudit: (limit = 50) =>
    request<ToolAuditEntry[]>(`/tools/audit?limit=${limit}`),

  getToolPolicy: () => request<ToolPolicyResponse>("/tools/policy"),

  updateTools: (data: Record<string, unknown>) =>
    request("/config/tools", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  // Logs
  getLogs: (limit = 200) => request<LogEntry[]>(`/logs?limit=${limit}`),

  // Security
  updateSecurity: (data: Record<string, unknown>) =>
    request("/config/security", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  getStatus: () => request<StatusResponse>("/status"),

  getConfig: () => request<FullConfig>("/config"),

  getOllamaModels: () => request<OllamaModel[]>("/ollama/models"),

  updateGeneral: (data: Record<string, unknown>) =>
    request("/config/general", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  resetSystemPrompt: () =>
    request<{ status: string; system_prompt: string }>(
      "/config/general/system-prompt/reset",
      { method: "POST" },
    ),

  updateLLM: (data: Record<string, unknown>) =>
    request("/config/llm", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  updateVoice: (data: Record<string, unknown>) =>
    request("/config/voice", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  enrollVoice: async (samples: Blob[]) => {
    const form = new FormData();
    samples.forEach((sample, index) => form.append("samples", sample, `voice-${index + 1}.wav`));
    const response = await fetch(`${BASE}/voice/enroll`, {
      method: "POST",
      credentials: "same-origin",
      body: form,
    });
    if (!response.ok) return responseError(response);
    return response.json() as Promise<VoiceProfileResponse>;
  },

  deleteVoiceProfile: () =>
    request<VoiceProfileResponse>("/voice/profile", { method: "DELETE" }),

  previewVoice: (options: VoicePreviewOptions) =>
    requestBlob("/voice/preview", options as unknown as Record<string, unknown>),

  updateWhatsApp: (data: Record<string, unknown>) =>
    request("/config/whatsapp", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  toggleVoice: (enabled: boolean) =>
    request("/voice/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),

  getMCPServers: () =>
    request<Record<string, unknown>>("/config/mcp/servers"),

  getMCPStatus: () => request<MCPServerStatus[]>("/mcp/status"),

  addMCPServer: (data: Record<string, unknown>) =>
    request("/config/mcp/servers", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateMCPServer: (name: string, data: Record<string, unknown>) =>
    request(`/config/mcp/servers/${encodeURIComponent(name)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteMCPServer: (name: string) =>
    request<void>(`/config/mcp/servers/${encodeURIComponent(name)}`, { method: "DELETE" }),

  reconnectMCPServer: (name: string) =>
    request<{ status: string; tools: number }>(
      `/config/mcp/servers/${encodeURIComponent(name)}/reconnect`,
      { method: "POST" },
    ),

  // dax-system shell allowlist
  getShellAllow: () => request<ShellAllowResponse>("/config/system/shell-allow"),

  updateShellAllow: (commands: string[]) =>
    request<{ status: string; commands: string[] }>(
      "/config/system/shell-allow",
      { method: "PUT", body: JSON.stringify({ commands }) },
    ),

  // OAuth
  startMCPAuth: (name: string) =>
    request<{ authorization_url: string; state: string }>(
      `/mcp/${encodeURIComponent(name)}/auth/start`,
      { method: "POST" },
    ),

  getMCPAuthStatus: (name: string) =>
    request<{ authenticated: boolean; expired?: boolean }>(
      `/mcp/${encodeURIComponent(name)}/auth/status`,
    ),

  logoutMCP: (name: string) =>
    request(`/mcp/${encodeURIComponent(name)}/auth/logout`, { method: "POST" }),

  // LLM model discovery
  listLLMModels: (provider?: string) =>
    request<Record<string, string[]>>(`/llm/models${provider ? `?provider=${provider}` : ""}`),

  // Memory management
  listMemory: () => request<MemoryEntry[]>("/memory"),
  getMemory: (slug: string) => request<MemoryEntry>(`/memory/${slug}`),
  createMemory: (data: { name: string; body: string; description?: string; type?: string }) =>
    request<MemoryEntry>("/memory", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateMemory: (
    slug: string,
    data: { name?: string; body?: string; description?: string; type?: string },
  ) =>
    request<{ status: string }>(`/memory/${slug}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteMemory: (slug: string) =>
    request<void>(`/memory/${encodeURIComponent(slug)}`, { method: "DELETE" }),

  // Codex / Claude config generators
  getCodexConfig: () => request<{ toml: string; server_count: number; note: string }>("/codex-config"),
  getClaudeConfig: () => request<{ json: string; server_count: number; note: string }>("/claude-config"),

  // MCP marketplace
  getMCPPresets: () => request<MCPPreset[]>("/mcp/presets"),
  searchMCPRegistry: (q: string, limit = 30) =>
    request<{ servers: RegistryServer[]; count?: number; error?: string }>(
      `/mcp/registry/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),

  // Telegram
  updateTelegram: (data: Record<string, unknown>) =>
    request("/config/telegram", { method: "PATCH", body: JSON.stringify(data) }),

  updateWeb: (data: Record<string, unknown>) =>
    request("/config/web", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  changePassword: (currentPassword: string, newPassword: string) =>
    request<{ status: string }>("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    }),

  // Conversation history
  listConversations: (limit = 50) =>
    request<ConversationSummary[]>(`/conversations?limit=${limit}`),

  getConversation: (id: string) =>
    request<ConversationDetail>(`/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<void>(`/conversations/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
