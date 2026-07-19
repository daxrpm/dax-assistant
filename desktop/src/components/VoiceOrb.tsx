import { useEffect, useRef } from "react";

/**
 * The voice orb — direction D, "Órbita".
 *
 * A ring of points circling a core; amplitude pushes them outward and makes
 * them brighter. Canvas 2D rather than WebGL: the workload is ~44 arcs per
 * frame against Canvas's several-thousand-draw budget, WebGL costs more on
 * cold start, and its driver clocks the GPU harder — the wrong trade for a
 * HUD that is idle most of the time.
 *
 * Two things keep it honest about cost:
 *
 *   - Level frames arrive at ~12.5 Hz from `/ws/voice`. Rendering is
 *     decoupled and interpolates toward the latest amplitude, so 60 fps comes
 *     from the spring, not from a faster socket.
 *   - When the pipeline is idle and the spring has settled, the loop stops
 *     via `cancelAnimationFrame` instead of spinning on a still image.
 */

export type OrbState = "idle" | "listening" | "processing" | "speaking";

interface VoiceOrbProps {
  /** Pipeline state; drives resting behaviour and colour weighting. */
  state: OrbState;
  /** Latest normalized amplitude 0–1, from a `/ws/voice` level frame. */
  level: number;
  /** Rendered diameter in CSS pixels. */
  size?: number;
}

const DOTS = 44;
const CORE_RADIUS_RATIO = 0.3;

/** Below this the spring has visually settled and we can stop drawing. */
const SETTLE_EPSILON = 0.002;

function readAccent(): string {
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue("--accent")
    .trim();
  return raw || "#6e8bff";
}

/** Parse `#rgb`/`#rrggbb` into an `r,g,b` string usable inside rgba(). */
function toRgbTriplet(hex: string): string {
  const clean = hex.replace("#", "");
  const full =
    clean.length === 3
      ? clean
          .split("")
          .map((c) => c + c)
          .join("")
      : clean;
  const n = Number.parseInt(full, 16);
  if (Number.isNaN(n)) return "110,139,255";
  return `${(n >> 16) & 255},${(n >> 8) & 255},${n & 255}`;
}

export function VoiceOrb({ state, level, size = 160 }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // Read through refs so a new level frame never restarts the render loop.
  const stateRef = useRef(state);
  const levelRef = useRef(level);

  stateRef.current = state;
  levelRef.current = level;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = size * dpr;
    canvas.height = size * dpr;
    ctx.scale(dpr, dpr);

    const rgb = toRgbTriplet(readAccent());
    let frame = 0;
    let spin = 0;
    let amp = 0;

    const draw = () => {
      const current = stateRef.current;
      const idle = current === "idle";

      // Idle keeps a slow breath so the orb reads as alive but not busy.
      const target = idle
        ? 0.05
        : current === "processing"
          ? 0.22
          : Math.max(0.08, Math.min(1, levelRef.current));

      amp += (target - amp) * 0.16;
      spin += idle ? 0.0016 : 0.005;

      const cx = size / 2;
      const cy = size / 2;
      const core = size * CORE_RADIUS_RATIO;
      ctx.clearRect(0, 0, size, size);

      for (let i = 0; i < DOTS; i++) {
        const angle = (i / DOTS) * Math.PI * 2 + spin;
        // Per-dot phase so the ring shimmers rather than pulsing as one block.
        const pulse = Math.abs(Math.sin(frame * 0.03 + i * 0.4));
        const distance = core + size * 0.06 + amp * size * 0.2 * pulse;
        const radius = size * 0.008 + amp * size * 0.014 * pulse;
        ctx.beginPath();
        ctx.arc(cx + Math.cos(angle) * distance, cy + Math.sin(angle) * distance, radius, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${rgb},${(0.28 + pulse * amp * 0.72).toFixed(3)})`;
        ctx.fill();
      }

      ctx.beginPath();
      ctx.arc(cx, cy, core, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${rgb},${(0.07 + amp * 0.14).toFixed(3)})`;
      ctx.fill();

      ctx.beginPath();
      ctx.arc(cx, cy, core * (1 + amp * 0.06), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${rgb},${(0.55 + amp * 0.35).toFixed(3)})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();

      frame += 1;

      // Idle and settled: stop. A still orb must not hold a rAF loop open.
      const settled = idle && Math.abs(target - amp) < SETTLE_EPSILON;
      if (reduceMotion || settled) {
        raf = 0;
        return;
      }
      raf = requestAnimationFrame(draw);
    };

    let raf = requestAnimationFrame(draw);
    return () => {
      if (raf) cancelAnimationFrame(raf);
    };
    // Keyed on `state` so leaving idle restarts a loop that stopped itself.
    // Deliberately NOT keyed on `level`: frames arrive ~12.5×/s and are read
    // through a ref, so they must not tear down and rebuild the loop.
  }, [size, state]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: size, height: size, display: "block" }}
      role="img"
      aria-label={
        state === "listening"
          ? "Escuchando"
          : state === "speaking"
            ? "Dax está hablando"
            : state === "processing"
              ? "Procesando"
              : "En reposo"
      }
    />
  );
}
