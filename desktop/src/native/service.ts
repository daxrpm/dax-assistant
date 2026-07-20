import { invoke } from "@tauri-apps/api/core";

export type ServiceAction = "status" | "start" | "stop" | "restart" | "enable" | "disable" | "enable_now";
export type ServiceTarget = "backend" | "capability_node";

export interface ServiceStatus {
  unit: string;
  load_state: string;
  active_state: string;
  sub_state: string;
  unit_file_state: string;
}

export function controlService(
  target: ServiceTarget,
  action: ServiceAction,
): Promise<ServiceStatus> {
  return invoke<ServiceStatus>("service_control", { target, action });
}
