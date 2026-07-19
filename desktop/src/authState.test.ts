import { describe, expect, it } from "vitest";
import { permitsAuthenticatedShell } from "./authState";

describe("permitsAuthenticatedShell", () => {
  it("fails closed when auth status is missing or unauthenticated", () => {
    expect(permitsAuthenticatedShell(null)).toBe(false);
    expect(permitsAuthenticatedShell({ configured: true, auth_enabled: true, authenticated: false })).toBe(false);
  });

  it("allows authenticated and auth-disabled backends", () => {
    expect(permitsAuthenticatedShell({ configured: true, auth_enabled: true, authenticated: true })).toBe(true);
    expect(permitsAuthenticatedShell({ configured: false, auth_enabled: false, authenticated: false })).toBe(true);
  });
});
