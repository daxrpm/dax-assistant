import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createRemotePtt,
  encodePcm16,
  PcmFrameBatcher,
  RemoteMicrophone,
  resampleMono,
  StreamingMonoResampler,
} from "./remoteAudio";

afterEach(() => vi.unstubAllGlobals());

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

  it("batches worklet chunks into 20 ms PCM frames", () => {
    const batcher = new PcmFrameBatcher();
    expect(batcher.push(new Float32Array(200))).toEqual([]);
    const frames = batcher.push(new Float32Array(440));
    expect(frames).toHaveLength(2);
    expect(frames[0]?.byteLength).toBe(640);
  });
});

describe("remote microphone lifecycle", () => {
  it("stops a stream whose permission request resolves after cancellation", async () => {
    let resolvePermission!: (stream: MediaStream) => void;
    const permission = new Promise<MediaStream>((resolve) => {
      resolvePermission = resolve;
    });
    const stopTrack = vi.fn();
    const getUserMedia = vi.fn(() => permission);
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia },
    });
    const microphone = new RemoteMicrophone();
    const starting = microphone.start(vi.fn());

    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalledOnce());
    await microphone.stop();
    resolvePermission({ getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream);
    await starting;

    expect(stopTrack).toHaveBeenCalledOnce();
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
