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
    const text = await response.text();
    throw new ApiError(response.status, `API error ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
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

export interface MCPServerStatus {
  name: string;
  connected: boolean;
  transport: string;
  enabled: boolean;
  tool_count: number;
  tools: string[];
}

export interface ToolPolicyResponse {
  default: string;
  allow: string[];
  ask: string[];
  deny: string[];
  confirm_timeout_seconds: number;
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
    request<{ ok: boolean }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    }),

  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),

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
    request(`/config/mcp/servers/${name}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteMCPServer: (name: string) =>
    request(`/config/mcp/servers/${name}`, { method: "DELETE" }),

  reconnectMCPServer: (name: string) =>
    request<{ status: string; tools: number }>(
      `/config/mcp/servers/${name}/reconnect`,
      { method: "POST" },
    ),

  // OAuth
  startMCPAuth: (name: string) =>
    request<{ authorization_url: string; state: string }>(
      `/mcp/${name}/auth/start`,
      { method: "POST" },
    ),

  getMCPAuthStatus: (name: string) =>
    request<{ authenticated: boolean; expired?: boolean }>(
      `/mcp/${name}/auth/status`,
    ),

  logoutMCP: (name: string) =>
    request(`/mcp/${name}/auth/logout`, { method: "POST" }),

  // LLM model discovery
  listLLMModels: (provider?: string) =>
    request<Record<string, string[]>>(`/llm/models${provider ? `?provider=${provider}` : ""}`),

  // Memory management
  listMemory: () => request<MemoryEntry[]>("/memory"),
  getMemory: (slug: string) => request<MemoryEntry>(`/memory/${slug}`),
  updateMemory: (slug: string, data: { body: string; description?: string }) =>
    request<{ status: string }>(`/memory/${slug}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteMemory: (slug: string) =>
    fetch(`${BASE}/memory/${slug}`, { method: "DELETE", credentials: "same-origin" }),

  // Codex config generator
  getCodexConfig: () => request<{ toml: string; server_count: number; note: string }>("/codex-config"),

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
    fetch(`${BASE}/conversations/${id}`, {
      method: "DELETE",
      credentials: "same-origin",
    }),
};
