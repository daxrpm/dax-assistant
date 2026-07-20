import { describe, expect, it } from "vitest";
import { canAdvanceOnboarding, ONBOARDING_STEPS } from "./Onboarding";

describe("onboarding flow", () => {
  it("has all required first-run steps", () => {
    expect(ONBOARDING_STEPS).toBe(5);
  });

  it("blocks the configuration step until strategy URLs are valid", () => {
    expect(canAdvanceOnboarding(2, "local", "http://127.0.0.1:8420", "")).toBe(true);
    expect(canAdvanceOnboarding(2, "local", "https://example.com", "")).toBe(false);
    expect(canAdvanceOnboarding(2, "remote", "http://127.0.0.1:8420", "http://remote.example")).toBe(false);
    expect(canAdvanceOnboarding(2, "remote", "http://127.0.0.1:8420", "https://remote.example")).toBe(true);
  });
});
