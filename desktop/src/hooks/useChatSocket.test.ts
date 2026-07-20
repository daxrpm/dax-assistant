import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  COMMAND_DECK_SESSION_ID,
  CHAT_MESSAGE_LIMIT,
  CHAT_STORE_LIMIT,
  createChatStore,
  getChatStore,
  shouldAcceptChatFrame,
  shutdownChatStores,
} from "./useChatSocket";

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

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }
}

describe("chat session pool", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    shutdownChatStores();
    vi.unstubAllGlobals();
  });

  it("accepts only frames for the store's session", () => {
    expect(shouldAcceptChatFrame({ type: "message" }, "active")).toBe(false);
    expect(shouldAcceptChatFrame({ session_id: "active" }, "active")).toBe(true);
    expect(shouldAcceptChatFrame({ session_id: "other" }, "active")).toBe(false);
  });

  it("uses one store per session and reserves a separate deck session", () => {
    expect(getChatStore("chat-a")).toBe(getChatStore("chat-a"));
    expect(getChatStore("chat-a")).not.toBe(getChatStore("chat-b"));
    expect(getChatStore(COMMAND_DECK_SESSION_ID)).not.toBe(getChatStore("chat-a"));
  });

  it("routes sends and incoming messages without crossing sessions", () => {
    const a = createChatStore("a");
    const b = createChatStore("b");
    const unsubscribeA = a.subscribe(() => undefined);
    const unsubscribeB = b.subscribe(() => undefined);
    const socketA = FakeWebSocket.instances[0];
    const socketB = FakeWebSocket.instances[1];
    socketA?.onopen?.();
    socketB?.onopen?.();

    expect(socketA?.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_subscribe", session_ids: ["a"] }),
    );
    expect(socketB?.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_subscribe", session_ids: ["b"] }),
    );

    a.send("from a");
    b.send("from b");
    expect(socketA?.send).toHaveBeenCalledWith(expect.stringContaining('"session_id":"a"'));
    expect(socketB?.send).toHaveBeenCalledWith(expect.stringContaining('"session_id":"b"'));

    act(() => {
      socketA?.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({
          type: "message",
          role: "assistant",
          content: "only a",
          session_id: "a",
        }),
      }));
      socketB?.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({
          type: "message",
          role: "assistant",
          content: "wrong",
          session_id: "a",
        }),
      }));
    });

    expect(a.getSnapshot().messages.at(-1)?.content).toBe("only a");
    expect(b.getSnapshot().messages.some((message) => message.content === "wrong")).toBe(false);
    unsubscribeA();
    unsubscribeB();
    a.shutdown();
    b.shutdown();
    expect(socketA?.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_unsubscribe", session_ids: ["a"] }),
    );
    expect(socketB?.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_unsubscribe", session_ids: ["b"] }),
    );
  });

  it("restores the subscription after reconnecting", () => {
    vi.useFakeTimers();
    const store = createChatStore("restored");
    const unsubscribe = store.subscribe(() => undefined);
    const first = FakeWebSocket.instances[0]!;
    first.onopen?.();
    first.onclose?.({ code: 1006 } as CloseEvent);
    vi.advanceTimersByTime(2000);
    const second = FakeWebSocket.instances[1]!;
    second.onopen?.();

    expect(first.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_subscribe", session_ids: ["restored"] }),
    );
    expect(second.send).toHaveBeenCalledWith(
      JSON.stringify({ type: "session_subscribe", session_ids: ["restored"] }),
    );
    unsubscribe();
    store.shutdown();
    vi.useRealTimers();
  });

  it("ignores callbacks from a replaced socket", () => {
    vi.useFakeTimers();
    const store = createChatStore("a");
    const unsubscribe = store.subscribe(() => undefined);
    const first = FakeWebSocket.instances[0]!;
    first.onclose?.({ code: 1006 } as CloseEvent);
    vi.advanceTimersByTime(2000);
    const second = FakeWebSocket.instances[1]!;
    second.onopen?.();

    first.onclose?.({ code: 1008 } as CloseEvent);
    expect(store.getSnapshot()).toMatchObject({ status: "open", authFailed: false });

    unsubscribe();
    store.shutdown();
    vi.useRealTimers();
  });

  it("closes a socket that never completes its connection", () => {
    vi.useFakeTimers();
    const store = createChatStore("a");
    const unsubscribe = store.subscribe(() => undefined);
    vi.advanceTimersByTime(5000);
    expect(FakeWebSocket.instances[0]?.close).toHaveBeenCalledOnce();
    unsubscribe();
    store.shutdown();
    vi.useRealTimers();
  });

  it("keeps an active turn connected across navigation until its answer arrives", () => {
    vi.useFakeTimers();
    const store = createChatStore("active-turn");
    const unsubscribe = store.subscribe(() => undefined);
    const socket = FakeWebSocket.instances[0]!;
    socket.onopen?.();
    store.send("use a tool");

    unsubscribe();
    act(() => vi.advanceTimersByTime(0));
    expect(socket.close).not.toHaveBeenCalled();

    act(() => socket.onmessage?.(new MessageEvent("message", {
      data: JSON.stringify({
        type: "message",
        role: "assistant",
        content: "finished",
        session_id: "active-turn",
      }),
    })));
    expect(socket.close).toHaveBeenCalledOnce();
    vi.useRealTimers();
  });

  it("bounds messages and evicts the least recently used session store", () => {
    const messages = Array.from({ length: CHAT_MESSAGE_LIMIT + 1 }, (_, index) => ({
      id: String(index),
      role: "user" as const,
      content: String(index),
      timestamp: "2026-01-01T00:00:00Z",
    }));
    expect(createChatStore("bounded", messages).getSnapshot().messages).toHaveLength(
      CHAT_MESSAGE_LIMIT,
    );

    const oldest = getChatStore("session-0");
    for (let index = 1; index <= CHAT_STORE_LIMIT; index += 1) {
      getChatStore(`session-${index}`);
    }
    expect(getChatStore("session-0")).not.toBe(oldest);
  });
});
