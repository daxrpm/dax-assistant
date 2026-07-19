import { invoke } from "@tauri-apps/api/core";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { isTauriRuntime } from "./environment";

export type WindowFramePreference = "native" | "custom";
export type WindowResizeDirection =
  | "East"
  | "North"
  | "NorthEast"
  | "NorthWest"
  | "South"
  | "SouthEast"
  | "SouthWest"
  | "West";

export async function getWindowFrame(): Promise<WindowFramePreference> {
  if (!isTauriRuntime()) return "custom";
  return invoke<WindowFramePreference>("window_frame_get");
}

export async function setWindowFrame(
  frame: WindowFramePreference,
): Promise<WindowFramePreference> {
  if (!isTauriRuntime()) return frame;
  return invoke<WindowFramePreference>("window_frame_set", { frame });
}

export async function minimizeMainWindow(): Promise<void> {
  if (isTauriRuntime()) await invoke("main_window_minimize");
}

export async function toggleMaximizeMainWindow(): Promise<boolean> {
  if (!isTauriRuntime()) return false;
  return invoke<boolean>("main_window_toggle_maximize");
}

export async function hideMainWindow(): Promise<void> {
  if (isTauriRuntime()) await invoke("main_window_hide");
}

export async function startMainWindowDragging(): Promise<void> {
  if (isTauriRuntime()) await getCurrentWindow().startDragging();
}

export async function startMainWindowResize(
  direction: WindowResizeDirection,
): Promise<void> {
  if (isTauriRuntime()) {
    await getCurrentWindow().startResizeDragging(direction);
  }
}
