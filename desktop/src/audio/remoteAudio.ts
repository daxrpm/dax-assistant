import { usesRemoteAudio } from "../api/connection";
import { voiceStore, type VoiceStore } from "../hooks/useVoiceSocket";

const TARGET_RATE = 16_000;

export function resampleMono(input: Float32Array, sourceRate: number): Float32Array {
  if (sourceRate === TARGET_RATE) return input.slice();
  if (sourceRate < TARGET_RATE || sourceRate <= 0) {
    throw new Error("Microphone sample rate must be at least 16 kHz");
  }
  const ratio = sourceRate / TARGET_RATE;
  const output = new Float32Array(Math.floor(input.length / ratio));
  for (let index = 0; index < output.length; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(input.length, Math.floor((index + 1) * ratio));
    let sum = 0;
    for (let sample = start; sample < end; sample += 1) sum += input[sample] ?? 0;
    output[index] = sum / Math.max(1, end - start);
  }
  return output;
}

export function encodePcm16(input: Float32Array): ArrayBuffer {
  const output = new ArrayBuffer(input.length * 2);
  const view = new DataView(output);
  input.forEach((value, index) => {
    const clipped = Math.max(-1, Math.min(1, value));
    view.setInt16(index * 2, clipped < 0 ? clipped * 32768 : clipped * 32767, true);
  });
  return output;
}

export class StreamingMonoResampler {
  private buffer = new Float32Array(0);
  private position = 0;

  constructor(private readonly sourceRate: number) {
    if (sourceRate < TARGET_RATE || sourceRate <= 0) {
      throw new Error("Microphone sample rate must be at least 16 kHz");
    }
  }

  process(input: Float32Array): Float32Array {
    if (this.sourceRate === TARGET_RATE) return input.slice();
    const combined = new Float32Array(this.buffer.length + input.length);
    combined.set(this.buffer);
    combined.set(input, this.buffer.length);
    const ratio = this.sourceRate / TARGET_RATE;
    const output: number[] = [];
    while (this.position < combined.length - 1) {
      const left = Math.floor(this.position);
      const fraction = this.position - left;
      const first = combined[left] ?? 0;
      const second = combined[left + 1] ?? first;
      output.push(first + (second - first) * fraction);
      this.position += ratio;
    }
    const consumed = Math.min(Math.floor(this.position), Math.max(0, combined.length - 1));
    this.buffer = combined.slice(consumed);
    this.position -= consumed;
    return Float32Array.from(output);
  }
}

export class RemoteMicrophone {
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: AudioWorkletNode | ScriptProcessorNode | null = null;

  async start(send: (frame: ArrayBuffer) => void): Promise<void> {
    await this.stop();
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      video: false,
    });
    this.stream = stream;
    try {
      const context = new AudioContext();
      this.context = context;
      const source = context.createMediaStreamSource(stream);
      this.source = source;
      const resampler = new StreamingMonoResampler(context.sampleRate);
      const forward = (samples: Float32Array) => {
        const resampled = resampler.process(samples);
        if (resampled.length) send(encodePcm16(resampled));
      };

      if (context.audioWorklet && typeof AudioWorkletNode !== "undefined") {
        await context.audioWorklet.addModule("/pcm-worklet.js");
        const processor = new AudioWorkletNode(context, "dax-pcm-processor");
        processor.port.onmessage = (event: MessageEvent<Float32Array>) => forward(event.data);
        source.connect(processor);
        processor.connect(context.destination);
        this.processor = processor;
      } else {
        const processor = context.createScriptProcessor(2048, 1, 1);
        processor.onaudioprocess = (event) => forward(event.inputBuffer.getChannelData(0));
        source.connect(processor);
        processor.connect(context.destination);
        this.processor = processor;
      }
      await context.resume();
    } catch (error) {
      await this.stop();
      throw error;
    }
  }

  async stop(): Promise<void> {
    if (this.processor) {
      this.processor.disconnect();
      if ("port" in this.processor) this.processor.port.onmessage = null;
      if ("onaudioprocess" in this.processor) this.processor.onaudioprocess = null;
    }
    this.source?.disconnect();
    for (const track of this.stream?.getTracks() ?? []) track.stop();
    const context = this.context;
    this.processor = null;
    this.source = null;
    this.stream = null;
    this.context = null;
    if (context && context.state !== "closed") await context.close();
  }
}

export function createRemotePtt(
  store: VoiceStore,
  microphone: RemoteMicrophone,
) {
  let held = false;
  const controller = {
    async press() {
      if (held) return;
      held = true;
      try {
        await store.acquireRemoteAudio();
        await store.startRemoteAudio();
        await microphone.start(store.sendPcm);
      } catch (error) {
        held = false;
        await microphone.stop();
        await store.cancelRemoteAudio();
        throw error;
      }
    },
    async release() {
      if (!held) return;
      held = false;
      await microphone.stop();
      await store.stopRemoteAudio();
    },
    async cancel() {
      held = false;
      await microphone.stop();
      await store.cancelRemoteAudio();
    },
  };
  store.onRemoteDisconnect?.(() => {
    held = false;
    void microphone.stop();
  });
  return controller;
}

const remotePtt = createRemotePtt(voiceStore, new RemoteMicrophone());

export const pushToTalk = {
  press: async (localPress: () => Promise<unknown>) =>
    usesRemoteAudio() ? remotePtt.press() : localPress(),
  release: async (localRelease: () => Promise<unknown>) =>
    usesRemoteAudio() ? remotePtt.release() : localRelease(),
};
