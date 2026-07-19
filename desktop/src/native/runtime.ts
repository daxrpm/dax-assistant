import { emit, listen, type UnlistenFn } from "@tauri-apps/api/event";
import { api } from "../api/client";
import { pushToTalk } from "../audio/remoteAudio";
import { toggleVoiceHud } from "./hud";
import { sendNativeNotification } from "./notifications";
export { isTauriRuntime } from "./environment";

export interface DesktopRuntimeSnapshot {
  pttError: string | null;
}

interface RuntimeDependencies {
  listen: typeof listen;
  emit: typeof emit;
  press: () => Promise<unknown>;
  release: () => Promise<unknown>;
  showHud: () => Promise<unknown>;
  toggleVoice: () => Promise<unknown>;
  notifyError: (message: string) => Promise<void>;
}

export function createDesktopRuntime(deps: RuntimeDependencies) {
  let snapshot: DesktopRuntimeSnapshot = { pttError: null };
  let startPromise: Promise<void> | null = null;
  let unlisten: UnlistenFn[] = [];
  let requests = Promise.resolve();
  let controlsPtt = false;
  let notifiedError: string | null = null;
  const subscribers = new Set<() => void>();

  const updateError = (pttError: string | null) => {
    snapshot = { pttError };
    if (pttError === null) notifiedError = null;
    for (const subscriber of subscribers) subscriber();
  };
  const message = (error: unknown) =>
    error instanceof Error ? error.message : String(error);
  const report = (error: unknown) => {
    const text = message(error);
    updateError(text);
    void deps.emit("hotkey://push-to-talk-error", text).catch(() => undefined);
    if (notifiedError !== text) {
      notifiedError = text;
      void deps.notifyError(text).catch(() => undefined);
    }
  };
  const enqueue = (operation: () => Promise<unknown>) => {
    requests = requests.then(operation).then(
      () => undefined,
      (error) => report(error),
    );
  };

  const start = (handlePtt: boolean) => {
    controlsPtt ||= handlePtt;
    if (startPromise) return startPromise;
    startPromise = Promise.all([
      deps.listen("hotkey://push-to-talk-down", () => {
        updateError(null);
        if (controlsPtt) enqueue(deps.press);
      }),
      deps.listen("hotkey://push-to-talk-up", () => {
        if (controlsPtt) enqueue(deps.release);
      }),
      deps.listen<string>("hotkey://push-to-talk-error", (event) => {
        updateError(event.payload);
      }),
      deps.listen("tray://talk-to-dax", () => {
        enqueue(deps.showHud);
      }),
      deps.listen("tray://toggle-voice-listening", () => {
        enqueue(deps.toggleVoice);
      }),
    ])
      .then((cleanups) => {
        unlisten = cleanups;
      })
      .catch((error) => {
        startPromise = null;
        report(error);
      });
    return startPromise;
  };

  return {
    start,
    stop() {
      for (const cleanup of unlisten) cleanup();
      unlisten = [];
      startPromise = null;
    },
    subscribe(subscriber: () => void) {
      subscribers.add(subscriber);
      return () => {
        subscribers.delete(subscriber);
      };
    },
    getSnapshot: () => snapshot,
  };
}

export const desktopRuntime = createDesktopRuntime({
  listen,
  emit,
  press: () => pushToTalk.press(api.pushToTalkPress),
  release: () => pushToTalk.release(api.pushToTalkRelease),
  showHud: toggleVoiceHud,
  toggleVoice: async () => {
    const status = await api.status();
    return api.toggleVoice(!status.voice_listening);
  },
  notifyError: (message) => sendNativeNotification("Dax needs attention", message),
});
