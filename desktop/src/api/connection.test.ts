import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  authoritativeHealthIdentity,
  connectionCandidates,
  getWsUrl,
  isLoopbackUrl,
  loadConnectionSettings,
  loadToken,
  currentToken,
  resolveConnection,
  saveConnectionSettings,
  storeToken,
  tokenStorageKey,
  validateBaseUrl,
} from "./connection";

const HEALTH = {
  status: "ok",
  instance_id: "authority-1",
  role: "authoritative",
  api_protocol: "dax",
  api_version: 1,
  liveness: true,
  readiness: true,
} as const;

function healthResponse(instanceId: string = HEALTH.instance_id): Response {
  return new Response(JSON.stringify({ ...HEALTH, instance_id: instanceId }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("validateBaseUrl", () => {
  it("allows loopback HTTP and normalizes trailing slashes", () => {
    expect(validateBaseUrl(" http://localhost:8420/// ")).toBe("http://localhost:8420");
  });

  it("requires HTTPS for a public host", () => {
    expect(() => validateBaseUrl("http://example.com")).toThrow(/private address/);
    expect(validateBaseUrl("https://example.com/")).toBe("https://example.com");
    expect(() => validateBaseUrl("https://example.com/api/")).toThrow(/path/);
  });

  it("allows cleartext to a private address, matching Android and Tauri", () => {
    expect(validateBaseUrl("http://192.168.1.50:8420")).toBe("http://192.168.1.50:8420");
    expect(validateBaseUrl("http://10.0.0.4:8420")).toBe("http://10.0.0.4:8420");
    expect(validateBaseUrl("http://172.16.0.1:8420")).toBe("http://172.16.0.1:8420");
    expect(validateBaseUrl("http://172.31.255.254:8420")).toBe("http://172.31.255.254:8420");
    expect(validateBaseUrl("http://[fd00::1]:8420")).toBe("http://[fd00::1]:8420");
  });

  it("allows the overlay range Tailscale assigns from", () => {
    expect(validateBaseUrl("http://100.64.0.2:8420")).toBe("http://100.64.0.2:8420");
    expect(validateBaseUrl("http://100.127.255.254:8420")).toBe("http://100.127.255.254:8420");
    // 100.63 and 100.128 bracket RFC 6598.
    expect(() => validateBaseUrl("http://100.63.0.1:8420")).toThrow(/private address/);
    expect(() => validateBaseUrl("http://100.128.0.1:8420")).toThrow(/private address/);
  });

  it("keeps cleartext off addresses that can route publicly", () => {
    // 172.15 and 172.32 bracket the private range; a DNS name never qualifies
    // because it can be repointed at a public address.
    expect(() => validateBaseUrl("http://172.15.0.1:8420")).toThrow(/private address/);
    expect(() => validateBaseUrl("http://172.32.0.1:8420")).toThrow(/private address/);
    expect(() => validateBaseUrl("http://8.8.8.8:8420")).toThrow(/private address/);
    expect(() => validateBaseUrl("http://home-server:8420")).toThrow(/private address/);
    expect(() => validateBaseUrl("http://[2001:db8::1]:8420")).toThrow(/private address/);
  });

  it("rejects credentials, queries and non-HTTP protocols", () => {
    expect(() => validateBaseUrl("https://user:secret@example.com")).toThrow(/credentials/);
    expect(() => validateBaseUrl("https://example.com?q=1")).toThrow(/query/);
    expect(() => validateBaseUrl("file:///tmp/dax")).toThrow(/private address|scheme/);
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

  it("always returns a single authority candidate", () => {
    expect(connectionCandidates("local", "http://localhost:8420", "https://dax.example")).toEqual([
      "http://localhost:8420",
    ]);
    expect(connectionCandidates("remote", "http://localhost:8420", "https://dax.example")).toEqual([
      "https://dax.example",
    ]);
  });

  it("accepts only ready authoritative Dax health", () => {
    const health = HEALTH;
    expect(authoritativeHealthIdentity(health)).toBe("authority-1");
    expect(authoritativeHealthIdentity({ ...health, readiness: false })).toBeNull();
    expect(authoritativeHealthIdentity({ ...health, role: "edge" })).toBeNull();
  });

  it("migrates browser version 2 hybrid settings to remote-only version 3", async () => {
    localStorage.setItem("dax.backend.settings.v2", JSON.stringify({
      version: 2,
      strategy: "hybrid",
      local_url: "http://127.0.0.1:8420",
      remote_url: "https://dax.example",
      active_url: "http://127.0.0.1:8420",
      onboarding_complete: true,
    }));

    const migrated = await loadConnectionSettings();

    expect(migrated).toMatchObject({
      version: 3,
      strategy: "remote",
      active_url: "https://dax.example",
      active_server_id: null,
    });
    expect(localStorage.getItem("dax.backend.settings.v2")).toBeNull();
  });

  it("discards origin-only tokens when a v2 migration first pins an identity", async () => {
    localStorage.setItem("dax.backend.settings.v2", JSON.stringify({
      version: 2,
      strategy: "hybrid",
      local_url: "http://127.0.0.1:8420",
      remote_url: "https://dax.example",
      active_url: "http://127.0.0.1:8420",
      onboarding_complete: true,
    }));
    const legacyKey = `dax.session.token:${encodeURIComponent("https://dax.example")}`;
    sessionStorage.setItem(legacyKey, "unsafe-origin-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(healthResponse());

    await loadConnectionSettings();
    const resolution = await resolveConnection(false, () => undefined);

    expect(resolution.server_instance_id).toBe("authority-1");
    expect(currentToken()).toBeNull();
    expect(sessionStorage.getItem(legacyKey)).toBeNull();
  });

  it("isolates browser tokens by origin and instance identity", async () => {
    localStorage.setItem("dax.backend.settings.v3", JSON.stringify({
      version: 3,
      strategy: "remote",
      local_url: "http://127.0.0.1:8420",
      remote_url: "https://one.example",
      active_url: "https://one.example",
      active_server_id: "authority-1",
      onboarding_complete: true,
    }));
    await loadConnectionSettings();
    expect(tokenStorageKey("https://one.example/api")).toBe(tokenStorageKey("https://one.example/other"));
    expect(tokenStorageKey("https://one.example")).not.toBe(tokenStorageKey("https://two.example"));
  });

  it("does not load a pinned token until health validates the authority", async () => {
    localStorage.setItem("dax.backend.settings.v3", JSON.stringify({
      version: 3,
      strategy: "remote",
      local_url: "http://127.0.0.1:8420",
      remote_url: "https://dax.example",
      active_url: "https://dax.example",
      active_server_id: "authority-1",
      onboarding_complete: true,
    }));
    await loadConnectionSettings();
    sessionStorage.setItem(tokenStorageKey(), "pinned-token");

    expect(await loadToken()).toBeNull();
    expect(currentToken()).toBeNull();

    vi.spyOn(globalThis, "fetch").mockResolvedValue(healthResponse());
    await resolveConnection(false, () => undefined);
    expect(currentToken()).toBe("pinned-token");
  });

  it("rejects a same-origin replacement and clears its pinned credential", async () => {
    localStorage.setItem("dax.backend.settings.v3", JSON.stringify({
      version: 3,
      strategy: "remote",
      local_url: "http://127.0.0.1:8420",
      remote_url: "https://dax.example",
      active_url: "https://dax.example",
      active_server_id: "authority-1",
      onboarding_complete: true,
    }));
    await loadConnectionSettings();
    const key = tokenStorageKey();
    sessionStorage.setItem(key, "authority-one-token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(healthResponse("malicious-replacement"));

    await expect(resolveConnection(false, () => undefined)).rejects.toThrow(/identity changed/);
    expect(currentToken()).toBeNull();
    expect(sessionStorage.getItem(key)).toBeNull();
  });

  it("preserves the identity pin on an unchanged normalized settings save", async () => {
    localStorage.setItem("dax.backend.settings.v3", JSON.stringify({
      version: 3,
      strategy: "remote",
      local_url: "http://127.0.0.1:8420",
      remote_url: "https://dax.example",
      active_url: "https://dax.example",
      active_server_id: "authority-1",
      onboarding_complete: true,
    }));
    await loadConnectionSettings();

    const saved = await saveConnectionSettings({
      strategy: "remote",
      localUrl: "http://127.0.0.1:8420/",
      remoteUrl: "https://dax.example/",
      onboardingComplete: true,
    });

    expect(saved.active_server_id).toBe("authority-1");
  });

  it("clears active credentials before an explicit authority switch", async () => {
    localStorage.setItem("dax.backend.settings.v3", JSON.stringify({
      version: 3,
      strategy: "remote",
      local_url: "http://127.0.0.1:8420",
      remote_url: "https://old.example",
      active_url: "https://old.example",
      active_server_id: "authority-1",
      onboarding_complete: true,
    }));
    await loadConnectionSettings();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(healthResponse());
    await resolveConnection(false, () => undefined);
    await storeToken("old-token");
    const oldKey = tokenStorageKey();

    const saved = await saveConnectionSettings({
      strategy: "remote",
      localUrl: "http://127.0.0.1:8420",
      remoteUrl: "https://new.example",
      onboardingComplete: true,
    });

    expect(sessionStorage.getItem(oldKey)).toBeNull();
    expect(currentToken()).toBeNull();
    expect(saved.active_server_id).toBeNull();
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
