import { describe, expect, it, vi } from "vitest";
import { createDesktopRuntime } from "./runtime";

describe("desktop push-to-talk runtime", () => {
  it("installs listeners once and serializes press before release", async () => {
    const callbacks = new Map<string, (event: { payload: string }) => void>();
    const listen = vi.fn(async (name: string, callback: (event: { payload: string }) => void) => {
      callbacks.set(name, callback);
      return vi.fn();
    });
    const order: string[] = [];
    const runtime = createDesktopRuntime({
      listen: listen as never,
      emit: vi.fn(async () => undefined) as never,
      press: vi.fn(async () => {
        order.push("press");
        return { status: "ok", state: "listening" };
      }),
      release: vi.fn(async () => {
        order.push("release");
        return { status: "ok", state: "processing" };
      }),
      showHud: vi.fn(async () => undefined),
      toggleVoice: vi.fn(async () => undefined),
      notifyError: vi.fn(async () => undefined),
    });

    await Promise.all([runtime.start(true), runtime.start(true)]);
    expect(listen).toHaveBeenCalledTimes(5);
    callbacks.get("hotkey://push-to-talk-down")?.({ payload: "" });
    callbacks.get("hotkey://push-to-talk-up")?.({ payload: "" });

    await vi.waitFor(() => expect(order).toEqual(["press", "release"]));
  });

  it("surfaces API failures in the shared snapshot", async () => {
    const callbacks = new Map<string, (event: { payload: string }) => void>();
    const emit = vi.fn(async () => undefined);
    const runtime = createDesktopRuntime({
      listen: vi.fn(async (name: string, callback: (event: { payload: string }) => void) => {
        callbacks.set(name, callback);
        return vi.fn();
      }) as never,
      emit: emit as never,
      press: vi.fn(async () => {
        throw new Error("Voice input is not available");
      }),
      release: vi.fn(async () => ({ status: "ok", state: "idle" })),
      showHud: vi.fn(async () => undefined),
      toggleVoice: vi.fn(async () => undefined),
      notifyError: vi.fn(async () => undefined),
    });
    await runtime.start(true);

    callbacks.get("hotkey://push-to-talk-down")?.({ payload: "" });

    await vi.waitFor(() =>
      expect(runtime.getSnapshot().pttError).toBe("Voice input is not available"),
    );
    expect(emit).toHaveBeenCalledWith(
      "hotkey://push-to-talk-error",
      "Voice input is not available",
    );
  });

  it("routes tray events through frontend operations once", async () => {
    const callbacks = new Map<string, (event: { payload: string }) => void>();
    const showHud = vi.fn(async () => undefined);
    const toggleVoice = vi.fn(async () => undefined);
    const runtime = createDesktopRuntime({
      listen: vi.fn(async (name: string, callback: (event: { payload: string }) => void) => {
        callbacks.set(name, callback);
        return vi.fn();
      }) as never,
      emit: vi.fn(async () => undefined) as never,
      press: vi.fn(async () => undefined),
      release: vi.fn(async () => undefined),
      showHud,
      toggleVoice,
      notifyError: vi.fn(async () => undefined),
    });

    await Promise.all([runtime.start(true), runtime.start(true)]);
    callbacks.get("tray://talk-to-dax")?.({ payload: "" });
    callbacks.get("tray://toggle-voice-listening")?.({ payload: "" });

    await vi.waitFor(() => expect(showHud).toHaveBeenCalledTimes(1));
    expect(toggleVoice).toHaveBeenCalledTimes(1);
  });
});
