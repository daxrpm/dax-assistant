import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createDuckingDispatcher,
  getMediaDuckingEnabled,
  mapVoiceToDuckingState,
  MEDIA_DUCKING_STORAGE_KEY,
  setMediaDuckingEnabled,
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

  it("serializes transitions and deduplicates repeated states", async () => {
    const order: string[] = [];
    const send = vi.fn(async (state: string) => {
      await Promise.resolve();
      order.push(state);
    });
    const dispatch = createDuckingDispatcher(send);
    void dispatch("listening");
    void dispatch("listening");
    await dispatch("speaking");
    expect(send).toHaveBeenCalledTimes(2);
    expect(order).toEqual(["listening", "speaking"]);
  });
});
