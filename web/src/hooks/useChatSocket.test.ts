import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { shouldAcceptChatFrame, useChatSocket } from "./useChatSocket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static OPEN = 1;
  readyState = FakeWebSocket.OPEN;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  close = vi.fn();
  send = vi.fn();
  readonly url: string;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
}

describe("useChatSocket session protocol", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("accepts only frames carrying the exact active session", () => {
    expect(shouldAcceptChatFrame({ session_id: "active" }, "active")).toBe(true);
    expect(shouldAcceptChatFrame({ session_id: "other" }, "active")).toBe(false);
    expect(shouldAcceptChatFrame({}, "active")).toBe(false);
  });

  it("subscribes on open and transfers ownership when the session changes", () => {
    const { rerender, unmount } = renderHook(
      ({ sessionId }) => useChatSocket(sessionId),
      { initialProps: { sessionId: "one" } },
    );
    const socket = FakeWebSocket.instances[0]!;
    act(() => socket.onopen?.());
    expect(socket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_subscribe", session_ids: ["one"] }),
    );

    rerender({ sessionId: "two" });
    expect(socket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_unsubscribe", session_ids: ["one"] }),
    );
    expect(socket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_subscribe", session_ids: ["two"] }),
    );

    unmount();
    expect(socket.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_unsubscribe", session_ids: ["two"] }),
    );
  });

  it("filters another session before processing messages and confirmations", () => {
    const { result, unmount } = renderHook(() => useChatSocket("active"));
    const socket = FakeWebSocket.instances[0]!;
    act(() => {
      socket.onopen?.();
      socket.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({
          type: "message",
          role: "assistant",
          content: "leaked",
          session_id: "other",
        }),
      }));
      socket.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({
          type: "tool_confirmation_request",
          approval_id: "foreign",
          session_id: "other",
        }),
      }));
    });

    expect(result.current.messages).toEqual([]);
    expect(result.current.confirmation).toBeNull();
    unmount();
  });

  it("does not reconnect after an authentication failure", () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(() => useChatSocket("active"));
    const socket = FakeWebSocket.instances[0]!;
    act(() => socket.onclose?.({ code: 1008 } as CloseEvent));
    act(() => vi.advanceTimersByTime(10_000));

    expect(FakeWebSocket.instances).toHaveLength(1);
    unmount();
  });
});
