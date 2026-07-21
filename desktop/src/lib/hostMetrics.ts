import { currentToken, getBaseUrl, isTauri } from "../api/connection";
import {
  getNativeSystemMetrics,
  type NativeSystemMetrics,
} from "../native/metrics";

export interface HostMetrics {
  cpu: number;
  memory: number;
  disk: number;
  uptimeSeconds: number;
}

interface ServerResourceUsage {
  total_bytes: number;
  used_bytes: number;
  available_bytes: number;
  percent: number;
}

interface ServerSystemMetrics {
  cpu_percent: number;
  cpu_count: number;
  memory: ServerResourceUsage;
  disk: ServerResourceUsage;
  uptime_seconds: number;
}

const fraction = (percent: number) => Math.max(0, Math.min(1, percent / 100));

export function normalizeNativeMetrics(metrics: NativeSystemMetrics): HostMetrics {
  const disk =
    metrics.disks.find((entry) => entry.mount_point === "/") ??
    metrics.disks.find((entry) => !entry.removable) ??
    metrics.disks[0];
  return {
    cpu: fraction(metrics.cpu_usage_percent),
    memory:
      metrics.memory_total_bytes > 0
        ? metrics.memory_used_bytes / metrics.memory_total_bytes
        : 0,
    disk:
      disk && disk.total_bytes > 0
        ? (disk.total_bytes - disk.available_bytes) / disk.total_bytes
        : 0,
    uptimeSeconds: metrics.uptime_seconds,
  };
}

export function normalizeServerMetrics(metrics: ServerSystemMetrics): HostMetrics {
  return {
    cpu: fraction(metrics.cpu_percent),
    memory: fraction(metrics.memory.percent),
    disk: fraction(metrics.disk.percent),
    uptimeSeconds: metrics.uptime_seconds,
  };
}

export function isLoopbackBackend(baseUrl = getBaseUrl()): boolean {
  if (!baseUrl) return true;
  try {
    const host = new URL(baseUrl).hostname.toLowerCase();
    return host === "localhost" || host === "127.0.0.1" || host === "[::1]";
  } catch {
    return false;
  }
}

export async function readClientMetrics(): Promise<HostMetrics | null> {
  if (!isTauri()) return null;
  return normalizeNativeMetrics(await getNativeSystemMetrics());
}

export async function readServerMetrics(): Promise<HostMetrics> {
  const token = currentToken();
  const response = await fetch(`${getBaseUrl()}/api/system/metrics`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    credentials: "include",
  });
  if (!response.ok) throw new Error(`Metrics request failed (${response.status})`);
  return normalizeServerMetrics((await response.json()) as ServerSystemMetrics);
}
