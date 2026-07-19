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
});
