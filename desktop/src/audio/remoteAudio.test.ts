import { describe, expect, it, vi } from "vitest";
import {
  createRemotePtt,
  encodePcm16,
  resampleMono,
  StreamingMonoResampler,
} from "./remoteAudio";

describe("remote audio encoding", () => {
  it("resamples mono audio to 16 kHz", () => {
    const input = new Float32Array([0, 0.5, 1, 0.5, 0, -0.5]);
    expect(Array.from(resampleMono(input, 48_000))).toEqual([0.5, 0]);
  });

  it("preserves fractional phase across worklet chunks", () => {
    const resampler = new StreamingMonoResampler(48_000);
    const first = resampler.process(new Float32Array(128));
    const second = resampler.process(new Float32Array(128));
    expect(first.length + second.length).toBe(85);
  });

  it("clips and writes signed PCM16 little endian", () => {
    const encoded = encodePcm16(new Float32Array([-2, -1, 0, 1, 2]));
    const view = new DataView(encoded);
    expect(Array.from({ length: 5 }, (_, index) => view.getInt16(index * 2, true))).toEqual([
      -32768, -32768, 0, 32767, 32767,
    ]);
  });
});

describe("remote PTT cleanup", () => {
  it("always stops capture and cancels the lease after permission failure", async () => {
    const store = {
      acquireRemoteAudio: vi.fn(async () => undefined),
      startRemoteAudio: vi.fn(async () => undefined),
      stopRemoteAudio: vi.fn(async () => undefined),
      cancelRemoteAudio: vi.fn(async () => undefined),
      sendPcm: vi.fn(),
    };
    const microphone = {
      start: vi.fn(async () => { throw new DOMException("denied", "NotAllowedError"); }),
      stop: vi.fn(async () => undefined),
    };
    const ptt = createRemotePtt(store as never, microphone as never);
    await expect(ptt.press()).rejects.toThrow("denied");
    expect(microphone.stop).toHaveBeenCalled();
    expect(store.cancelRemoteAudio).toHaveBeenCalled();
  });

  it("stops tracks before asking the server to process", async () => {
    const order: string[] = [];
    const store = {
      acquireRemoteAudio: vi.fn(async () => undefined),
      startRemoteAudio: vi.fn(async () => undefined),
      stopRemoteAudio: vi.fn(async () => { order.push("server-stop"); }),
      cancelRemoteAudio: vi.fn(async () => undefined),
      sendPcm: vi.fn(),
    };
    const microphone = {
      start: vi.fn(async () => undefined),
      stop: vi.fn(async () => { order.push("mic-stop"); }),
    };
    const ptt = createRemotePtt(store as never, microphone as never);
    await ptt.press();
    await ptt.release();
    expect(order).toEqual(["mic-stop", "server-stop"]);
  });

  it("stops capture immediately when the voice socket disconnects", async () => {
    let disconnected: (() => void) | undefined;
    const store = {
      acquireRemoteAudio: vi.fn(async () => undefined),
      startRemoteAudio: vi.fn(async () => undefined),
      stopRemoteAudio: vi.fn(async () => undefined),
      cancelRemoteAudio: vi.fn(async () => undefined),
      sendPcm: vi.fn(),
      onRemoteDisconnect: vi.fn((listener: () => void) => {
        disconnected = listener;
        return () => undefined;
      }),
    };
    const microphone = {
      start: vi.fn(async () => undefined),
      stop: vi.fn(async () => undefined),
    };
    const ptt = createRemotePtt(store as never, microphone as never);
    await ptt.press();
    disconnected?.();
    await vi.waitFor(() => expect(microphone.stop).toHaveBeenCalled());
  });
});
