import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { LevelFrame } from "../hooks/useVoiceSocket";

export type OrbState = "idle" | "listening" | "processing" | "speaking";

export interface VoiceOrbHandle {
  setLevel(frame: LevelFrame): void;
}

interface VoiceOrbProps {
  state: OrbState;
  size?: number;
  ariaLabel: string;
}

type LevelSource = LevelFrame["source"];

export interface SignalBuffer {
  rms: Float32Array;
  spectrum: Float32Array;
  cursor: number;
  peak: number;
}

const HISTORY_SIZE = 48;
const SPECTRUM_SIZE = 12;
const SETTLE_EPSILON = 0.002;
const VELOCITY_EPSILON = 0.003;
const PARTICLES = 34;

export function createSignalBuffers(): Record<LevelSource, SignalBuffer> {
  const create = (): SignalBuffer => ({
    rms: new Float32Array(HISTORY_SIZE),
    spectrum: new Float32Array(SPECTRUM_SIZE),
    cursor: 0,
    peak: 0,
  });
  return { input: create(), output: create() };
}

const clamp = (value: number) =>
  Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;

export function pushLevelFrame(
  buffers: Record<LevelSource, SignalBuffer>,
  frame: LevelFrame,
) {
  const signal = buffers[frame.source];
  signal.peak = clamp(frame.peak);
  for (const sample of frame.rms) {
    signal.rms[signal.cursor] = clamp(sample);
    signal.cursor = (signal.cursor + 1) % signal.rms.length;
  }
  signal.spectrum.fill(0);
  frame.spectrum.slice(0, signal.spectrum.length).forEach((sample, index) => {
    signal.spectrum[index] = clamp(sample);
  });
}

export function advanceSpring(
  value: number,
  velocity: number,
  target: number,
  deltaSeconds: number,
): [number, number] {
  const dt = Math.max(0, Math.min(0.05, deltaSeconds));
  const nextVelocity =
    (velocity + (target - value) * 120 * dt) * Math.exp(-18 * dt);
  return [value + nextVelocity * dt, nextVelocity];
}

function readAccent(): string {
  return (
    getComputedStyle(document.documentElement).getPropertyValue("--accent").trim() ||
    "#6e8bff"
  );
}

function toRgb(hex: string): [number, number, number] {
  const clean = hex.replace("#", "");
  const full = clean.length === 3
    ? clean.split("").map((character) => character + character).join("")
    : clean;
  const value = Number.parseInt(full, 16);
  return Number.isNaN(value)
    ? [110, 139, 255]
    : [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

const rgba = ([red, green, blue]: [number, number, number], alpha: number) =>
  `rgba(${red},${green},${blue},${Math.max(0, Math.min(1, alpha)).toFixed(3)})`;

function drawWave(
  context: CanvasRenderingContext2D,
  signal: SignalBuffer,
  cx: number,
  cy: number,
  baseRadius: number,
  amplitude: number,
  rgb: [number, number, number],
  source: LevelSource,
) {
  const points = 64;
  context.beginPath();
  for (let index = 0; index <= points; index += 1) {
    const angle = (index / points) * Math.PI * 2;
    const historyIndex =
      (signal.cursor + Math.floor((index / points) * signal.rms.length)) %
      signal.rms.length;
    const envelope = signal.rms[historyIndex] ?? 0;
    const band = signal.spectrum[index % signal.spectrum.length] ?? 0;
    const harmonic = Math.sin(angle * (source === "input" ? 7 : 4));
    const energy = envelope * 0.58 + band * 0.27 + signal.peak * 0.15;
    const radius = baseRadius + amplitude * energy * baseRadius *
      (source === "input" ? 0.46 + harmonic * 0.12 : 0.25 + harmonic * 0.07);
    const x = cx + Math.cos(angle) * radius;
    const y = cy + Math.sin(angle) * radius * (source === "input" ? 0.94 : 0.72);
    if (index === 0) context.moveTo(x, y);
    else context.lineTo(x, y);
  }
  context.closePath();
  context.lineWidth = source === "input" ? 1.35 : 1;
  context.strokeStyle = rgba(rgb, source === "input" ? 0.64 * amplitude : 0.42 * amplitude);
  context.stroke();
}

export const VoiceOrb = forwardRef<VoiceOrbHandle, VoiceOrbProps>(function VoiceOrb(
  { state, size = 160, ariaLabel },
  ref,
) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef(state);
  const signalsRef = useRef(createSignalBuffers());
  const startRef = useRef<() => void>(() => undefined);
  stateRef.current = state;

  useImperativeHandle(
    ref,
    () => ({
      setLevel(frame) {
        pushLevelFrame(signalsRef.current, frame);
        if (stateRef.current !== "idle") startRef.current();
      },
    }),
    [],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reducedMotion = media.matches;
    let width = size;
    let height = size;
    let raf = 0;
    let lastTime = 0;
    let phase = 0;
    let inputAmplitude = 0;
    let outputAmplitude = 0;
    let inputVelocity = 0;
    let outputVelocity = 0;
    const rgb = toRgb(readAccent());

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      width = bounds.width || size;
      height = bounds.height || size;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.round(width * dpr));
      canvas.height = Math.max(1, Math.round(height * dpr));
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
      startRef.current();
    };

    const targets = (): [number, number] => {
      const current = stateRef.current;
      if (current === "idle") return [0, 0];
      if (current === "speaking") return [0.12, Math.max(0.18, signalsRef.current.output.peak)];
      if (current === "listening") return [Math.max(0.18, signalsRef.current.input.peak), 0.08];
      return [0.14, 0.14];
    };

    const paint = () => {
      const cx = width / 2;
      const cy = height / 2;
      const scale = Math.min(width, height);
      const core = scale * 0.245;
      const activity = Math.max(inputAmplitude, outputAmplitude);
      context.clearRect(0, 0, width, height);

      const shadow = context.createRadialGradient(cx, cy + core * 0.72, core * 0.15, cx, cy + core * 0.72, core * 1.55);
      shadow.addColorStop(0, "rgba(0,0,0,0.5)");
      shadow.addColorStop(1, "rgba(0,0,0,0)");
      context.save();
      context.scale(1, 0.32);
      context.fillStyle = shadow;
      context.beginPath();
      context.arc(cx, (cy + core * 1.55) / 0.32, core * 1.55, 0, Math.PI * 2);
      context.fill();
      context.restore();

      drawWave(context, signalsRef.current.input, cx, cy, core * 1.56, inputAmplitude, rgb, "input");
      drawWave(context, signalsRef.current.output, cx, cy, core * 1.22, outputAmplitude, rgb, "output");

      const particles = Array.from({ length: PARTICLES }, (_, index) => {
        const angle = (index / PARTICLES) * Math.PI * 2 + phase * (0.1 + (index % 3) * 0.025);
        return { index, angle, z: Math.sin(angle * 1.37 + index * 0.9) };
      }).sort((a, b) => a.z - b.z);

      const drawParticle = ({ index, angle, z }: (typeof particles)[number]) => {
        const orbit = core * (1.4 + (index % 4) * 0.16);
        const x = cx + Math.cos(angle) * orbit;
        const y = cy + Math.sin(angle) * orbit * (0.35 + (index % 3) * 0.07);
        const radius = scale * (0.004 + (z + 1) * 0.0025) * (0.8 + activity * 0.35);
        context.beginPath();
        context.arc(x, y, radius, 0, Math.PI * 2);
        context.fillStyle = rgba(rgb, 0.16 + (z + 1) * 0.18 + activity * 0.16);
        context.fill();
      };
      particles.filter((particle) => particle.z < 0).forEach(drawParticle);

      for (let ring = 0; ring < 3; ring += 1) {
        context.beginPath();
        context.ellipse(
          cx,
          cy,
          core * (1.3 + ring * 0.22),
          core * (0.32 + ring * 0.055),
          -0.28 + ring * 0.27 + phase * (ring === 1 ? -0.025 : 0.018),
          Math.PI,
          Math.PI * 2,
        );
        context.strokeStyle = rgba(rgb, 0.16 + ring * 0.07 + activity * 0.12);
        context.lineWidth = ring === 1 ? 1.3 : 0.8;
        context.stroke();
      }

      const sphere = context.createRadialGradient(
        cx - core * 0.34,
        cy - core * 0.42,
        core * 0.04,
        cx,
        cy,
        core * 1.1,
      );
      sphere.addColorStop(0, rgba(rgb, 0.92));
      sphere.addColorStop(0.2, rgba(rgb, 0.48 + activity * 0.18));
      sphere.addColorStop(0.62, rgba(rgb, 0.18 + activity * 0.12));
      sphere.addColorStop(1, "rgba(5,8,20,0.94)");
      context.beginPath();
      context.arc(cx, cy, core * (1 + activity * 0.035), 0, Math.PI * 2);
      context.fillStyle = sphere;
      context.shadowColor = rgba(rgb, 0.36 + activity * 0.25);
      context.shadowBlur = core * (0.28 + activity * 0.35);
      context.fill();
      context.shadowBlur = 0;

      const rim = context.createLinearGradient(cx, cy - core, cx, cy + core);
      rim.addColorStop(0, rgba(rgb, 0.72));
      rim.addColorStop(0.46, rgba(rgb, 0.18));
      rim.addColorStop(1, rgba(rgb, 0.04));
      context.beginPath();
      context.arc(cx, cy, core * 1.01, 0, Math.PI * 2);
      context.strokeStyle = rim;
      context.lineWidth = 1.2;
      context.stroke();

      for (let ring = 0; ring < 3; ring += 1) {
        context.beginPath();
        context.ellipse(
          cx,
          cy,
          core * (1.3 + ring * 0.22),
          core * (0.32 + ring * 0.055),
          -0.28 + ring * 0.27 + phase * (ring === 1 ? -0.025 : 0.018),
          0,
          Math.PI,
        );
        context.strokeStyle = rgba(rgb, 0.28 + ring * 0.08 + activity * 0.16);
        context.lineWidth = ring === 1 ? 1.45 : 0.9;
        context.stroke();
      }
      particles.filter((particle) => particle.z >= 0).forEach(drawParticle);
    };

    const draw = (time: number) => {
      raf = 0;
      const delta = lastTime === 0 ? 1 / 60 : Math.min(0.05, (time - lastTime) / 1000);
      lastTime = time;
      const [inputTarget, outputTarget] = targets();
      if (reducedMotion) {
        inputAmplitude = inputTarget;
        outputAmplitude = outputTarget;
        inputVelocity = 0;
        outputVelocity = 0;
      } else {
        [inputAmplitude, inputVelocity] = advanceSpring(inputAmplitude, inputVelocity, inputTarget, delta);
        [outputAmplitude, outputVelocity] = advanceSpring(outputAmplitude, outputVelocity, outputTarget, delta);
        phase += delta;
      }
      paint();
      const settled =
        stateRef.current === "idle" &&
        inputAmplitude < SETTLE_EPSILON &&
        outputAmplitude < SETTLE_EPSILON &&
        Math.abs(inputVelocity) < VELOCITY_EPSILON &&
        Math.abs(outputVelocity) < VELOCITY_EPSILON;
      if (!settled && !reducedMotion) raf = requestAnimationFrame(draw);
    };

    startRef.current = () => {
      if (!raf) {
        lastTime = 0;
        raf = requestAnimationFrame(draw);
      }
    };
    const onMotionChange = (event: MediaQueryListEvent) => {
      reducedMotion = event.matches;
      startRef.current();
    };
    media.addEventListener?.("change", onMotionChange);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    observer?.observe(canvas);
    window.addEventListener("resize", resize);
    resize();
    return () => {
      startRef.current = () => undefined;
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      media.removeEventListener?.("change", onMotionChange);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [size]);

  useEffect(() => {
    startRef.current();
  }, [state]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size, display: "block" }}
      role="img"
      aria-label={ariaLabel}
    />
  );
});
