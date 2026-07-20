import { act, cleanup, render } from "@testing-library/react";
import { createRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  advanceSpring,
  createSignalBuffers,
  getOrbVisualProfile,
  pushLevelFrame,
  VoiceOrb,
  type VoiceOrbHandle,
} from "./VoiceOrb";
import type { LevelFrame } from "../hooks/useVoiceSocket";

const frame = (source: LevelFrame["source"], peak = 0.8): LevelFrame => ({
  source,
  peak,
  rms: [0.1, 0.4, peak],
  spectrum: [0.2, 0.9, 0.35],
});

describe("VoiceOrb", () => {
  let frames: FrameRequestCallback[];
  let now: number;

  beforeEach(() => {
    frames = [];
    now = 0;
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      frames.push(callback);
      return frames.length;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.stubGlobal("matchMedia", () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const gradient = { addColorStop: vi.fn() };
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      arc: vi.fn(),
      beginPath: vi.fn(),
      closePath: vi.fn(),
      clearRect: vi.fn(),
      createLinearGradient: vi.fn(() => gradient),
      createRadialGradient: vi.fn(() => gradient),
      ellipse: vi.fn(),
      fill: vi.fn(),
      lineTo: vi.fn(),
      moveTo: vi.fn(),
      restore: vi.fn(),
      save: vi.fn(),
      scale: vi.fn(),
      setTransform: vi.fn(),
      stroke: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  const step = () => {
    const callback = frames.shift();
    if (!callback) return;
    now += 16;
    callback(now);
  };

  it("stops at settled idle and restarts for active levels", () => {
    const ref = createRef<VoiceOrbHandle>();
    const view = render(<VoiceOrb ref={ref} state="idle" ariaLabel="Idle" />);
    act(step);
    expect(frames).toHaveLength(0);

    act(() => ref.current?.setLevel(frame("input")));
    expect(frames).toHaveLength(0);

    view.rerender(<VoiceOrb ref={ref} state="listening" ariaLabel="Listening" />);
    act(() => ref.current?.setLevel(frame("input")));
    expect(frames).toHaveLength(1);
    act(step);
    expect(frames).toHaveLength(1);

    view.rerender(<VoiceOrb ref={ref} state="idle" ariaLabel="Idle" />);
    act(() => {
      for (let index = 0; index < 300 && frames.length; index += 1) step();
    });
    expect(frames).toHaveLength(0);
  });

  it("keeps input and output frames in separate ring buffers", () => {
    const buffers = createSignalBuffers();
    pushLevelFrame(buffers, frame("input", 0.72));
    pushLevelFrame(buffers, frame("output", 0.31));

    expect(buffers.input.peak).toBe(0.72);
    expect(buffers.output.peak).toBe(0.31);
    expect(buffers.input.rms).not.toBe(buffers.output.rms);
    expect(buffers.input.spectrum[1]).toBeCloseTo(0.9);
    expect(buffers.output.spectrum[1]).toBeCloseTo(0.9);
  });

  it("uses a delta-time spring with similar results across frame rates", () => {
    const simulate = (delta: number) => {
      let value = 0;
      let velocity = 0;
      for (let elapsed = 0; elapsed < 1; elapsed += delta) {
        [value, velocity] = advanceSpring(value, velocity, 1, delta);
      }
      return value;
    };

    expect(Math.abs(simulate(1 / 60) - simulate(1 / 120))).toBeLessThan(0.03);
  });

  it("gives listening, thinking, and speaking distinct visual signatures", () => {
    const listening = getOrbVisualProfile("listening");
    const thinking = getOrbVisualProfile("processing");
    const speaking = getOrbVisualProfile("speaking");

    expect(listening.tone).toBe("--accent");
    expect(thinking.tone).toBe("--purple");
    expect(speaking.tone).toBe("--success");
    expect(thinking.phaseRate).toBeGreaterThan(speaking.phaseRate);
    expect(speaking.pulse).toBeGreaterThan(listening.pulse);
  });
});
