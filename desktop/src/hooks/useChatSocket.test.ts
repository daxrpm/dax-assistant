import { act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  COMMAND_DECK_SESSION_ID,
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
    expect(shouldAcceptChatFrame({ type: "message" }, "active")).toBe(true);
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

    a.send("from a");
    b.send("from b");
    expect(socketA?.send).toHaveBeenCalledWith(expect.stringContaining('"session_id":"a"'));
    expect(socketB?.send).toHaveBeenCalledWith(expect.stringContaining('"session_id":"b"'));

    act(() => {
      socketA?.onmessage?.(new MessageEvent("message", {
        data: JSON.stringify({ type: "message", role: "assistant", content: "only a" }),
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
  });
});
