import { invoke } from "@tauri-apps/api/core";
import { isTauriRuntime } from "./environment";

const ENABLED_KEY = "dax.desktop.notifications";

export type NotificationPermission = "granted" | "denied" | "prompt";
export type NotificationState =
  | { available: true; enabled: boolean; permission: NotificationPermission }
  | { available: false; enabled: false; permission: "unavailable"; reason: string };

function persistedEnabled(): boolean {
  try {
    return localStorage.getItem(ENABLED_KEY) === "true";
  } catch {
    return false;
  }
}

function persist(enabled: boolean): void {
  localStorage.setItem(ENABLED_KEY, String(enabled));
}

async function permission(): Promise<NotificationPermission> {
  const granted = await invoke<boolean | null>(
    "plugin:notification|is_permission_granted",
  );
  return granted === true ? "granted" : granted === false ? "denied" : "prompt";
}

export async function getNotifications(): Promise<NotificationState> {
  if (!isTauriRuntime()) {
    return {
      available: false,
      enabled: false,
      permission: "unavailable",
      reason: "Native notifications are only available in the installed desktop app.",
    };
  }
  const currentPermission = await permission();
  const enabled = persistedEnabled() && currentPermission === "granted";
  if (!enabled && persistedEnabled()) persist(false);
  return { available: true, enabled, permission: currentPermission };
}

/** Called only from the settings toggle's user gesture. */
export async function setNotifications(enabled: boolean): Promise<NotificationState> {
  if (!isTauriRuntime()) return getNotifications();
  if (!enabled) {
    persist(false);
    return getNotifications();
  }
  let currentPermission = await permission();
  if (currentPermission === "prompt") {
    currentPermission = await invoke<NotificationPermission>(
      "plugin:notification|request_permission",
    );
  }
  persist(currentPermission === "granted");
  return getNotifications();
}

export async function sendNativeNotification(title: string, body: string): Promise<void> {
  if (!isTauriRuntime() || !persistedEnabled()) return;
  if ((await permission()) !== "granted") return;
  await invoke("plugin:notification|notify", { options: { title, body } });
}

export interface DisconnectMonitor {
  check(): Promise<void>;
}

export function createDisconnectMonitor({
  probe,
  notify,
  onDisconnected,
  threshold = 3,
}: {
  probe: () => Promise<unknown>;
  notify: () => Promise<void>;
  onDisconnected?: () => Promise<void>;
  threshold?: number;
}): DisconnectMonitor {
  let failures = 0;
  let notified = false;
  return {
    async check() {
      try {
        await probe();
        failures = 0;
        notified = false;
      } catch {
        failures += 1;
        if (failures >= threshold && !notified) {
          notified = true;
          await notify();
          await onDisconnected?.();
        }
      }
    },
  };
}
