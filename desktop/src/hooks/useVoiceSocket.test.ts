import React from "react";
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createVoiceStore } from "./useVoiceSocket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  readyState = 1;
  bufferedAmount = 0;

  constructor(_url: string) {
    FakeWebSocket.instances.push(this);
  }
}

describe("voice store", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("multicasts one connection and preserves state across subscribers", () => {
    const store = createVoiceStore();
    const first = renderHook(() => React.useSyncExternalStore(store.subscribe, store.getSnapshot));
    const second = renderHook(() => React.useSyncExternalStore(store.subscribe, store.getSnapshot));
    expect(FakeWebSocket.instances).toHaveLength(1);

    act(() => {
      FakeWebSocket.instances[0]?.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({
          type: "state",
          data: { state: "listening", conversation_id: "voice-1" },
        }),
      }));
    });
    expect(first.result.current.state).toBe("listening");
    expect(second.result.current.conversationId).toBe("voice-1");

    first.unmount();
    second.unmount();
    expect(FakeWebSocket.instances[0]?.close).not.toHaveBeenCalled();
    act(() => store.shutdown());
    expect(FakeWebSocket.instances[0]?.close).toHaveBeenCalledOnce();
    expect(store.getSnapshot().state).toBe("listening");
  });

  it("runs the explicit remote control handshake and sends binary PCM", async () => {
    const store = createVoiceStore();
    const acquiring = store.acquireRemoteAudio();
    const ws = FakeWebSocket.instances[0];
    ws?.onopen?.();
    await vi.waitFor(() => expect(ws?.send).toHaveBeenCalledTimes(1));
    expect(JSON.parse(ws?.send.mock.calls[0]?.[0] as string).format).toEqual({
      sample_rate: 16_000,
      channels: 1,
      sample_format: "pcm_s16le",
    });
    expect(JSON.parse(ws?.send.mock.calls[0]?.[0] as string).output).toEqual({
      mode: "client_text",
    });
    ws?.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "remote_audio.acquired", data: {} }),
    }));
    await acquiring;

    const starting = store.startRemoteAudio();
    await vi.waitFor(() => expect(ws?.send).toHaveBeenCalledTimes(2));
    ws?.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "remote_audio.started", data: {} }),
    }));
    await starting;
    const pcm = new ArrayBuffer(4);
    store.sendPcm(pcm);
    expect(ws?.send).toHaveBeenLastCalledWith(pcm);
    store.shutdown();
  });

  it("drops PCM while the browser socket is backpressured", async () => {
    const store = createVoiceStore();
    const acquiring = store.acquireRemoteAudio();
    const ws = FakeWebSocket.instances[0]!;
    ws.onopen?.();
    await vi.waitFor(() => expect(ws.send).toHaveBeenCalledTimes(1));
    ws.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "remote_audio.acquired", data: {} }),
    }));
    await acquiring;
    const starting = store.startRemoteAudio();
    await vi.waitFor(() => expect(ws.send).toHaveBeenCalledTimes(2));
    ws.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "remote_audio.started", data: {} }),
    }));
    await starting;
    ws.send.mockClear();
    ws.bufferedAmount = 300_000;
    store.sendPcm(new ArrayBuffer(640));
    expect(ws.send).not.toHaveBeenCalled();
    store.shutdown();
  });

  it("rejects a connection waiter after the connection timeout", async () => {
    vi.useFakeTimers();
    const store = createVoiceStore();
    const acquiring = store.acquireRemoteAudio();
    const rejected = expect(acquiring).rejects.toThrow("Timed out connecting");
    await vi.advanceTimersByTimeAsync(5000);
    await rejected;
    expect(FakeWebSocket.instances[0]?.close).toHaveBeenCalledOnce();
    store.shutdown();
    vi.useRealTimers();
  });

  it("ignores a stale close after reconnecting", () => {
    vi.useFakeTimers();
    const store = createVoiceStore();
    const unsubscribe = store.subscribe(() => undefined);
    const first = FakeWebSocket.instances[0]!;
    first.onclose?.({ code: 1006 } as CloseEvent);
    vi.advanceTimersByTime(2000);
    const second = FakeWebSocket.instances[1]!;
    second.onopen?.();
    first.onclose?.({ code: 1008, reason: "stale" } as CloseEvent);
    expect(store.getSnapshot().connected).toBe(true);
    expect(store.getSnapshot().error).not.toBe("stale");
    unsubscribe();
    store.shutdown();
    vi.useRealTimers();
  });

  it("notifies remote capture cleanup during explicit shutdown", () => {
    const store = createVoiceStore();
    const disconnected = vi.fn();
    store.onRemoteDisconnect(disconnected);

    store.shutdown();

    expect(disconnected).toHaveBeenCalledOnce();
  });

  it("delivers complete source-separated level frames outside snapshot state", () => {
    const store = createVoiceStore();
    const snapshotListener = vi.fn();
    const levels = vi.fn();
    const unsubscribeSnapshot = store.subscribe(snapshotListener);
    const unsubscribeLevels = store.subscribeLevel(levels);
    const ws = FakeWebSocket.instances[0];
    ws?.onopen?.();
    snapshotListener.mockClear();

    const input = { source: "input", rms: [0.1, 0.2], peak: 0.4, spectrum: [0.8] };
    const output = { source: "output", rms: [0.5, 0.3], peak: 0.7, spectrum: [0.2] };
    ws?.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "level", data: input }),
    }));
    ws?.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "level", data: output }),
    }));

    expect(levels).toHaveBeenNthCalledWith(1, input);
    expect(levels).toHaveBeenNthCalledWith(2, output);
    expect(snapshotListener).not.toHaveBeenCalled();
    expect(store.getSnapshot()).not.toHaveProperty("level");
    unsubscribeLevels();
    unsubscribeSnapshot();
    store.shutdown();
  });

  it("tracks the sentence being spoken and clears it after speaking", () => {
    const store = createVoiceStore();
    const unsubscribe = store.subscribe(() => undefined);
    const ws = FakeWebSocket.instances[0];
    ws?.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "state", data: { state: "speaking" } }),
    }));
    ws?.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "speech", data: { text: "Esta frase suena ahora.", language: "es" } }),
    }));
    expect(store.getSnapshot().speech?.text).toBe("Esta frase suena ahora.");

    ws?.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({ type: "state", data: { state: "conversing" } }),
    }));
    expect(store.getSnapshot().speech).toBeNull();
    unsubscribe();
    store.shutdown();
  });
});
