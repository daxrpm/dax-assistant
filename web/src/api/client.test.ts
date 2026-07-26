import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";

describe("web API delete requests", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("accepts an empty 204 response through the shared request path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.deleteConversation("conversation/id")).resolves.toBeUndefined();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/conversations/conversation%2Fid",
      expect.objectContaining({ method: "DELETE", credentials: "same-origin" }),
    );
  });

  it("surfaces the backend detail for failed deletes", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Conversation is protected" }),
      { status: 409 },
    )));

    await expect(api.deleteConversation("protected")).rejects.toEqual(
      expect.objectContaining({
        name: "ApiError",
        status: 409,
        message: "Conversation is protected",
      } satisfies Partial<ApiError>),
    );
  });
});

describe("device pairing requests", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("keeps normal client pairing bodyless", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.pairDevice();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/devices/pair",
      expect.objectContaining({ method: "POST" }),
    );
    expect(fetchMock.mock.calls[0]?.[1]).not.toHaveProperty("body");
  });

  it("explicitly requests a capability-node pairing code", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await api.pairDevice("capability_node");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/devices/pair",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          kind: "capability_node",
          backend_url: window.location.origin,
        }),
      }),
    );
  });
});
