import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useSyncExternalStore,
} from "react";
import {
  createSignalBuffers,
  pushLevelFrame,
  VoiceOrb,
  type OrbState,
  type VoiceOrbHandle,
} from "../components/VoiceOrb";
import {
  useVoiceSocket,
  type LevelFrame,
  type PipelineState,
} from "../hooks/useVoiceSocket";
import { useI18n } from "../i18n/I18n";
import { desktopRuntime } from "./runtime";
import { hideVoiceHud } from "./hud";
import s from "./VoiceHud.module.css";

const labelKeys = {
  idle: "deck.idle",
  listening: "deck.listening",
  processing: "deck.processing",
  speaking: "deck.speaking",
  conversing: "deck.conversing",
} as const;

const orbState = (state: PipelineState): OrbState =>
  state === "conversing" ? "listening" : state;

interface WaveformHandle {
  push(frame: LevelFrame): void;
}

const WAVE_SETTLED = 0.002;

const Waveform = forwardRef<WaveformHandle, { state: PipelineState }>(
  function Waveform({ state }, ref) {
    const { t } = useI18n();
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const stateRef = useRef(state);
    const startRef = useRef<() => void>(() => undefined);
    const signalsRef = useRef(createSignalBuffers());
    stateRef.current = state;

    useImperativeHandle(
      ref,
      () => ({
        push(frame) {
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
      let width = 1;
      let height = 1;
      const displayed = {
        input: new Float32Array(48),
        output: new Float32Array(48),
      };
      let raf = 0;
      let lastTime = 0;
      const resize = () => {
        const bounds = canvas.getBoundingClientRect();
        width = bounds.width || canvas.clientWidth || 1;
        height = bounds.height || canvas.clientHeight || 1;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.max(1, Math.round(width * dpr));
        canvas.height = Math.max(1, Math.round(height * dpr));
        context.setTransform(dpr, 0, 0, dpr, 0, 0);
        startRef.current();
      };
      const draw = (time: number) => {
        raf = 0;
        const delta = lastTime === 0 ? 1 / 60 : Math.min(0.05, (time - lastTime) / 1000);
        lastTime = time;
        const idle = stateRef.current === "idle";
        const blend = 1 - Math.exp(-14 * delta);
        let maximum = 0;
        for (const source of ["input", "output"] as const) {
          const signal = signalsRef.current[source];
          const sourceWeight = stateRef.current === "speaking"
            ? (source === "output" ? 1 : 0.28)
            : (source === "input" ? 1 : 0.35);
          for (let index = 0; index < displayed[source].length; index += 1) {
            const sample = signal.rms[(signal.cursor + index) % signal.rms.length] ?? 0;
            const band = signal.spectrum[index % signal.spectrum.length] ?? 0;
            const target = idle ? 0 : (sample * 0.72 + band * 0.18 + signal.peak * 0.1) * sourceWeight;
            const current = displayed[source][index] ?? 0;
            const next = current + (target - current) * blend;
            displayed[source][index] = next;
            maximum = Math.max(maximum, next);
          }
        }

        context.clearRect(0, 0, width, height);
        const accent = getComputedStyle(document.documentElement)
          .getPropertyValue("--accent")
          .trim();
        for (const source of ["output", "input"] as const) {
          context.strokeStyle = accent;
          context.globalAlpha = source === "input" ? 0.9 : 0.42;
          context.lineWidth = source === "input" ? 1.8 : 1.1;
          context.beginPath();
          displayed[source].forEach((sample, index) => {
            const x = (index / (displayed[source].length - 1)) * width;
            const oscillation = Math.sin(index * (source === "input" ? 2.3 : 1.25));
            const lane = source === "input" ? height * 0.38 : height * 0.64;
            const y = lane + oscillation * sample * height * (source === "input" ? 0.3 : 0.2);
            if (index === 0) context.moveTo(x, y);
            else context.lineTo(x, y);
          });
          context.stroke();
        }
        context.globalAlpha = 1;
        if (maximum >= WAVE_SETTLED) raf = requestAnimationFrame(draw);
      };
      startRef.current = () => {
        if (!raf) {
          lastTime = 0;
          raf = requestAnimationFrame(draw);
        }
      };
      const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
      observer?.observe(canvas);
      window.addEventListener("resize", resize);
      resize();
      return () => {
        startRef.current = () => undefined;
        observer?.disconnect();
        window.removeEventListener("resize", resize);
        if (raf) cancelAnimationFrame(raf);
      };
    }, []);

    useEffect(() => {
      startRef.current();
    }, [state]);

    return (
      <canvas
        ref={canvasRef}
        className={s.waveform}
        role="img"
        aria-label={t("hud.voiceLevel")}
      />
    );
  },
);

export function VoiceHud() {
  const { t } = useI18n();
  const orbRef = useRef<VoiceOrbHandle>(null);
  const waveformRef = useRef<WaveformHandle>(null);
  const onLevel = useCallback((frame: LevelFrame) => {
    orbRef.current?.setLevel(frame);
    waveformRef.current?.push(frame);
  }, []);
  const voice = useVoiceSocket({ onLevel });
  const runtime = useSyncExternalStore(
    desktopRuntime.subscribe,
    desktopRuntime.getSnapshot,
    desktopRuntime.getSnapshot,
  );

  useEffect(() => {
    if (voice.state !== "idle" || runtime.pttError) return;
    const timeout = window.setTimeout(() => void hideVoiceHud(), 900);
    return () => window.clearTimeout(timeout);
  }, [runtime.pttError, voice.state]);

  return (
    <main className={s.hud}>
      <VoiceOrb
        ref={orbRef}
        state={orbState(voice.state)}
        size={124}
        ariaLabel={t(labelKeys[voice.state])}
      />
      <div className={s.detail}>
        <div className={s.status}>{t(labelKeys[voice.state])}</div>
        <Waveform ref={waveformRef} state={voice.state} />
        <div className={runtime.pttError ? s.error : s.transcript} role="status">
          {runtime.pttError ||
            voice.error ||
            voice.transcript?.text ||
            (voice.connected ? t("hud.ready") : t("common.connecting"))}
        </div>
      </div>
      <button
        className={s.close}
        type="button"
        aria-label={t("hud.hide")}
        onClick={() => void hideVoiceHud()}
      >
        ×
      </button>
    </main>
  );
}
