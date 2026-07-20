import { beforeEach, expect, it, vi } from "vitest";
import { api } from "./client";
import { loadConnectionSettings, resolveConnection, storeToken } from "./connection";

const health = {
  status: "ok",
  instance_id: "authority-1",
  role: "authoritative",
  api_protocol: "dax",
  api_version: 1,
  liveness: true,
  readiness: true,
};

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.restoreAllMocks();
});

it("never attaches credentials to authority health probes", async () => {
  localStorage.setItem("dax.backend.settings.v3", JSON.stringify({
    version: 3,
    strategy: "remote",
    local_url: "http://127.0.0.1:8420",
    remote_url: "https://dax.example",
    active_url: "https://dax.example",
    active_server_id: "authority-1",
    onboarding_complete: true,
  }));
  const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
    new Response(JSON.stringify(health), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  await loadConnectionSettings();
  await resolveConnection(false, () => undefined);
  await storeToken("secret-token");

  await api.health();

  const options = fetchMock.mock.calls.at(-1)?.[1];
  expect(options?.credentials).toBe("omit");
  expect(new Headers(options?.headers).has("Authorization")).toBe(false);
});
