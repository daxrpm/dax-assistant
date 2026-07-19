import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  clearMcpActivity,
  trackMcpActivity,
  useMcpActivity,
} from "./mcpActivity";

describe("MCP activity", () => {
  afterEach(() => {
    clearMcpActivity("session-a");
    clearMcpActivity("session-b");
    cleanup();
  });

  it("tracks concurrent servers until their matching tool result", () => {
    const active = renderHook(() => useMcpActivity());

    act(() => {
      trackMcpActivity("session-a", { type: "tool_call", tool: "search", server: "docs" });
      trackMcpActivity("session-b", { type: "tool_call", tool: "read", server: "files" });
    });
    expect([...active.result.current.servers]).toEqual(expect.arrayContaining(["docs", "files"]));

    act(() => {
      trackMcpActivity("session-a", { type: "tool_result", tool: "search", server: "docs" });
    });
    expect(active.result.current.servers.has("docs")).toBe(false);
    expect(active.result.current.servers.has("files")).toBe(true);
  });

  it("clears unfinished calls when the turn completes", () => {
    const active = renderHook(() => useMcpActivity());
    act(() => {
      trackMcpActivity("session-a", { type: "tool_call", tool: "run", server: "system" });
      trackMcpActivity("session-a", { type: "done" });
    });
    expect(active.result.current.servers.size).toBe(0);
    expect(active.result.current.tools.size).toBe(0);
  });

  it("tracks a tool even when the event omits its MCP server", () => {
    const active = renderHook(() => useMcpActivity());
    act(() => trackMcpActivity("session-a", { type: "tool_call", tool: "search" }));
    expect(active.result.current.tools.has("search")).toBe(true);
  });
});
