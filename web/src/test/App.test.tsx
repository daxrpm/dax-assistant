import { render, screen } from "@testing-library/react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import App from "../App";

function jsonResponse(data: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(""),
  } as Response);
}

beforeEach(() => {
  // Auth disabled so AuthGate renders the app; minimal data for the rest.
  globalThis.fetch = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/auth/status")) {
      return jsonResponse({
        auth_enabled: false,
        configured: true,
        authenticated: true,
      });
    }
    if (url.includes("/status")) {
      return jsonResponse({
        name: "Dax",
        version: "0.1.0",
        status: "running",
        voice_listening: false,
        llm_provider: "ollama",
        mcp_servers: 0,
        mcp_tools: 0,
      });
    }
    if (url.includes("/tools/audit")) return jsonResponse([]);
    return jsonResponse({});
  }) as unknown as typeof fetch;
});

describe("App", () => {
  it("renders the layout once authenticated", async () => {
    render(<App />);
    expect(await screen.findByText("Assistant")).toBeInTheDocument();
  });

  it("renders navigation links", async () => {
    render(<App />);
    expect(await screen.findByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Chat")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });
});
