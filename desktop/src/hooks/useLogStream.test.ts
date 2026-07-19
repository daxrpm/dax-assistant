import "@testing-library/jest-dom/vitest";
import { useSyncExternalStore } from "react";
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createLogStore } from "./useLogStream";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;

  constructor(_url: string) {
    FakeWebSocket.instances.push(this);
  }

  close = vi.fn();
}

describe("log store", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shares one socket across navigation and closes on app shutdown", () => {
    const store = createLogStore();
    const first = renderHook(() =>
      useSyncExternalStore(store.subscribe, store.getSnapshot),
    );
    const second = renderHook(() =>
      useSyncExternalStore(store.subscribe, store.getSnapshot),
    );

    expect(FakeWebSocket.instances).toHaveLength(1);
    first.unmount();
    expect(FakeWebSocket.instances[0]?.close).not.toHaveBeenCalled();
    second.unmount();
    expect(FakeWebSocket.instances[0]?.close).not.toHaveBeenCalled();
    act(() => store.shutdown());
    expect(FakeWebSocket.instances[0]?.close).toHaveBeenCalledOnce();
  });

  it("keeps live frames received before the REST seed and deduplicates overlap", () => {
    const store = createLogStore();
    const { result } = renderHook(() =>
      useSyncExternalStore(store.subscribe, store.getSnapshot),
    );
    const live = {
      ts: "2026-07-19T12:00:01Z",
      level: "info",
      logger: "dax",
      message: "live",
    };

    act(() => {
      FakeWebSocket.instances[0]?.onmessage?.(
        new MessageEvent("message", { data: JSON.stringify(live) }),
      );
    });
    act(() => {
      store.seed([
        {
          timestamp: "2026-07-19T12:00:00Z",
          level: "INFO",
          logger: "dax",
          message: "snapshot",
        },
        live,
      ]);
    });

    expect(result.current.logs.map((entry) => entry.message)).toEqual([
      "snapshot",
      "live",
    ]);
    store.shutdown();
  });

  it("batches live frames and ignores stale socket callbacks", () => {
    vi.useFakeTimers();
    const store = createLogStore();
    const unsubscribe = store.subscribe(() => undefined);
    const first = FakeWebSocket.instances[0]!;
    first.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ level: "info", message: "one" }),
    }));
    first.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ level: "info", message: "two" }),
    }));
    expect(store.getSnapshot().logs).toEqual([]);
    vi.advanceTimersByTime(16);
    expect(store.getSnapshot().logs.map((entry) => entry.message)).toEqual(["one", "two"]);

    first.onclose?.({ code: 1006 } as CloseEvent);
    vi.advanceTimersByTime(2000);
    const second = FakeWebSocket.instances[1]!;
    second.onopen?.();
    first.onclose?.({ code: 1008 } as CloseEvent);
    expect(store.getSnapshot().connected).toBe(true);
    unsubscribe();
    store.shutdown();
    vi.useRealTimers();
  });

  it("closes a log socket that never opens", () => {
    vi.useFakeTimers();
    const store = createLogStore();
    const unsubscribe = store.subscribe(() => undefined);
    vi.advanceTimersByTime(5000);
    expect(FakeWebSocket.instances[0]?.close).toHaveBeenCalledOnce();
    unsubscribe();
    store.shutdown();
    vi.useRealTimers();
  });
});
