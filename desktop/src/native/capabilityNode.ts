import { invoke } from "@tauri-apps/api/core";

export interface CapabilityNodeEnrollmentStatus {
  enrolled: boolean;
  endpoint: string | null;
  device_id: string | null;
  node_name: string | null;
}

export function enrollCapabilityNode(
  code: string,
  nodeName: string,
): Promise<CapabilityNodeEnrollmentStatus> {
  return invoke<CapabilityNodeEnrollmentStatus>("capability_node_enroll", {
    code,
    nodeName,
  });
}

export function getCapabilityNodeStatus(): Promise<CapabilityNodeEnrollmentStatus> {
  return invoke<CapabilityNodeEnrollmentStatus>("capability_node_status");
}
