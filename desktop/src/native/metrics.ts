import { invoke } from "@tauri-apps/api/core";

export interface NativeDiskMetrics {
  name: string;
  mount_point: string;
  total_bytes: number;
  available_bytes: number;
  removable: boolean;
}

export interface NativeSystemMetrics {
  cpu_usage_percent: number;
  logical_cpu_count: number;
  memory_total_bytes: number;
  memory_used_bytes: number;
  memory_available_bytes: number;
  uptime_seconds: number;
  disks: NativeDiskMetrics[];
}

export function getNativeSystemMetrics(): Promise<NativeSystemMetrics> {
  return invoke<NativeSystemMetrics>("system_metrics");
}
