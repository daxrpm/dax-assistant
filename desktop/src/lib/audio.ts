const TARGET_RATE = 16_000;

/**
 * Transcode a recorded blob to 16 kHz mono 16-bit PCM WAV.
 *
 * Ported from `web/src/lib/audio.ts`. `MediaRecorder` gives us WebM/Opus at the
 * device's native rate; the enrollment endpoint wants WAV at the pipeline's
 * rate, so decode, linearly resample, and write the RIFF header by hand.
 */
export async function toEnrollmentWav(blob: Blob): Promise<Blob> {
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await blob.arrayBuffer());
    const input = decoded.getChannelData(0);
    const outputLength = Math.max(
      1,
      Math.round((input.length * TARGET_RATE) / decoded.sampleRate),
    );
    const output = new Float32Array(outputLength);
    const ratio = decoded.sampleRate / TARGET_RATE;

    for (let index = 0; index < outputLength; index += 1) {
      const position = index * ratio;
      const left = Math.floor(position);
      const right = Math.min(left + 1, input.length - 1);
      const mix = position - left;
      output[index] = (input[left] ?? 0) * (1 - mix) + (input[right] ?? 0) * mix;
    }

    const buffer = new ArrayBuffer(44 + output.length * 2);
    const view = new DataView(buffer);
    writeText(view, 0, "RIFF");
    view.setUint32(4, 36 + output.length * 2, true);
    writeText(view, 8, "WAVEfmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, TARGET_RATE, true);
    view.setUint32(28, TARGET_RATE * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeText(view, 36, "data");
    view.setUint32(40, output.length * 2, true);
    output.forEach((sample, index) => {
      const clamped = Math.max(-1, Math.min(1, sample));
      view.setInt16(
        44 + index * 2,
        clamped < 0 ? clamped * 32768 : clamped * 32767,
        true,
      );
    });
    return new Blob([buffer], { type: "audio/wav" });
  } finally {
    await context.close();
  }
}

function writeText(view: DataView, offset: number, value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}
