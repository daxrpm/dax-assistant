import { beforeEach, describe, expect, it } from "vitest";
import {
  FIRST_RUN_PROVIDERS,
  FIRST_RUN_STEPS,
  canAdvanceFirstRun,
  isFirstRunComplete,
  markFirstRunComplete,
  providerNeedsKey,
  resetFirstRun,
} from "./FirstRun";

describe("first-run setup", () => {
  beforeEach(() => {
    resetFirstRun();
  });

  it("covers model, node, phone, and a summary", () => {
    expect(FIRST_RUN_STEPS).toBe(4);
  });

  it("offers a local provider so the flow is completable without a key", () => {
    expect(FIRST_RUN_PROVIDERS).toContain("ollama");
    expect(providerNeedsKey("ollama")).toBe(false);
    expect(providerNeedsKey("openai")).toBe(true);
  });

  it("blocks saving a hosted provider until a key is supplied", () => {
    expect(canAdvanceFirstRun(0, "openai", "", false)).toBe(false);
    expect(canAdvanceFirstRun(0, "openai", "  ", false)).toBe(false);
    expect(canAdvanceFirstRun(0, "openai", "sk-live", false)).toBe(true);
  });

  it("does not demand a key again once one is stored", () => {
    expect(canAdvanceFirstRun(0, "openai", "", true)).toBe(true);
  });

  it("never blocks the local provider", () => {
    expect(canAdvanceFirstRun(0, "ollama", "", false)).toBe(true);
  });

  it("only gates the model step", () => {
    for (const step of [1, 2, 3]) {
      expect(canAdvanceFirstRun(step, "openai", "", false)).toBe(true);
    }
  });

  it("remembers that setup finished", () => {
    expect(isFirstRunComplete()).toBe(false);
    markFirstRunComplete();
    expect(isFirstRunComplete()).toBe(true);
  });

  it("treats unavailable storage as done rather than trapping the user", () => {
    const original = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new Error("blocked");
      },
    });

    expect(isFirstRunComplete()).toBe(true);

    if (original) Object.defineProperty(window, "localStorage", original);
  });
});
