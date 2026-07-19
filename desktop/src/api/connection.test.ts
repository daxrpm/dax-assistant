import { describe, expect, it } from "vitest";
import {
  connectionCandidates,
  getWsUrl,
  isLoopbackUrl,
  saveConnectionSettings,
  tokenStorageKey,
  validateBaseUrl,
} from "./connection";

describe("validateBaseUrl", () => {
  it("allows loopback HTTP and normalizes trailing slashes", () => {
    expect(validateBaseUrl(" http://localhost:8420/// ")).toBe("http://localhost:8420");
  });

  it("requires HTTPS remotely", () => {
    expect(() => validateBaseUrl("http://example.com")).toThrow(/HTTPS/);
    expect(validateBaseUrl("https://example.com/api/")).toBe("https://example.com/api");
  });

  it("rejects credentials, queries and non-HTTP protocols", () => {
    expect(() => validateBaseUrl("https://user:secret@example.com")).toThrow(/credentials/);
    expect(() => validateBaseUrl("https://example.com?q=1")).toThrow(/query/);
    expect(() => validateBaseUrl("file:///tmp/dax")).toThrow(/HTTPS/);
  });

  it("classifies only explicit loopback hosts as local", () => {
    expect(isLoopbackUrl("http://127.0.0.1:8420")).toBe(true);
    expect(isLoopbackUrl("http://localhost:8420")).toBe(true);
    expect(isLoopbackUrl("https://192.168.1.10:8420")).toBe(false);
    expect(isLoopbackUrl("https://dax.example.com")).toBe(false);
  });

  it("requires loopback for a local URL", () => {
    expect(() => validateBaseUrl("https://example.com", true)).toThrow(/loopback/);
  });

  it("orders hybrid remote first and gives remote no fallback", () => {
    expect(connectionCandidates("hybrid", "http://localhost:8420", "https://dax.example")).toEqual([
      "https://dax.example",
      "http://localhost:8420",
    ]);
    expect(connectionCandidates("remote", "http://localhost:8420", "https://dax.example")).toEqual([
      "https://dax.example",
    ]);
  });

  it("isolates browser tokens by origin rather than path", () => {
    expect(tokenStorageKey("https://one.example/api")).toBe(tokenStorageKey("https://one.example/other"));
    expect(tokenStorageKey("https://one.example")).not.toBe(tokenStorageKey("https://two.example"));
  });

  it("derives WSS for a non-loopback backend", async () => {
    await saveConnectionSettings({
      strategy: "remote",
      localUrl: "http://127.0.0.1:8420",
      remoteUrl: "https://dax.example.com",
      onboardingComplete: true,
    });
    expect(getWsUrl("/ws/voice", "secret")).toBe(
      "wss://dax.example.com/ws/voice?token=secret",
    );
  });
});
