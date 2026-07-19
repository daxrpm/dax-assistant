import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createDuckingDispatcher,
  DEFAULT_MEDIA_DUCKING_LEVEL,
  getMediaDuckingEnabled,
  getMediaDuckingLevel,
  mapVoiceToDuckingState,
  MEDIA_DUCKING_STORAGE_KEY,
  MEDIA_DUCKING_LEVEL_STORAGE_KEY,
  setMediaDuckingEnabled,
  setMediaDuckingLevel,
} from "./mediaDucking";

describe("media ducking", () => {
  beforeEach(() => localStorage.clear());

  it("maps voice states and folds conversing into processing", () => {
    expect(mapVoiceToDuckingState("idle")).toBe("idle");
    expect(mapVoiceToDuckingState("listening")).toBe("listening");
    expect(mapVoiceToDuckingState("processing")).toBe("processing");
    expect(mapVoiceToDuckingState("speaking")).toBe("speaking");
    expect(mapVoiceToDuckingState("conversing")).toBe("processing");
  });

  it("defaults on and persists the local setting", () => {
    expect(getMediaDuckingEnabled()).toBe(true);
    setMediaDuckingEnabled(false);
    expect(localStorage.getItem(MEDIA_DUCKING_STORAGE_KEY)).toBe("false");
    expect(getMediaDuckingEnabled()).toBe(false);
  });

  it("defaults, bounds and persists the speaking volume", () => {
    expect(getMediaDuckingLevel()).toBe(DEFAULT_MEDIA_DUCKING_LEVEL);
    setMediaDuckingLevel(0.65);
    expect(localStorage.getItem(MEDIA_DUCKING_LEVEL_STORAGE_KEY)).toBe("0.65");
    expect(getMediaDuckingLevel()).toBe(0.65);
    setMediaDuckingLevel(4);
    expect(getMediaDuckingLevel()).toBe(1);
  });

  it("serializes transitions and deduplicates repeated states", async () => {
    const order: string[] = [];
    const send = vi.fn(async (state: string, _volumeFactor: number) => {
      await Promise.resolve();
      order.push(state);
    });
    const dispatch = createDuckingDispatcher(send);
    void dispatch("listening", 0.4);
    void dispatch("listening", 0.4);
    await dispatch("speaking", 0.4);
    expect(send).toHaveBeenCalledTimes(2);
    expect(order).toEqual(["listening", "speaking"]);
  });

  it("reapplies the same state when the configured level changes", async () => {
    const send = vi.fn(async () => undefined);
    const dispatch = createDuckingDispatcher(send);
    await dispatch("speaking", 0.4);
    await dispatch("speaking", 0.7);
    expect(send).toHaveBeenCalledTimes(2);
  });
});
