import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useI18n } from "../i18n/I18n";
import { isTauriRuntime } from "../native/environment";
import {
  controlMedia,
  getMediaStatus,
  listenMediaSpectrum,
  startMediaSpectrum,
  stopMediaSpectrum,
  type MediaAction,
  type MediaSnapshot,
  type MediaSpectrumFrame,
} from "../native/media";
import spotifyLogo from "../assets/spotify.svg";
import s from "./NowPlaying.module.css";

export type MediaProvider = "spotify" | "browser" | "generic";

function hashTrack(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function progressWaveform(title: string, artist: string): number[] {
  let seed = hashTrack(`${title}\u001f${artist}`);
  const count = 32 + seed % 17;
  return Array.from({ length: count }, () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return 22 + seed % 75;
  });
}

export function formatMediaTime(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return "--:--";
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

export function mediaProvider(player: string, identity?: string | null): MediaProvider {
  const value = `${player} ${identity ?? ""}`.toLowerCase();
  if (value.includes("spotify")) return "spotify";
  if (["brave", "chromium", "chrome", "firefox"].some((name) => value.includes(name))) {
    return "browser";
  }
  return "generic";
}

function ProviderIcon({ provider }: { provider: MediaProvider }) {
  if (provider === "spotify") return <img src={spotifyLogo} alt="" />;
  if (provider === "browser") {
    return <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.5" fill="none" stroke="currentColor"/><path d="M2.8 8h14.4M10 2.5c2 2.1 3 4.6 3 7.5s-1 5.4-3 7.5M10 2.5C8 4.6 7 7.1 7 10s1 5.4 3 7.5" fill="none" stroke="currentColor"/></svg>;
  }
  return <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M8 14.2V5.3l7-1.5v8.5M8 14.2a2.6 2.6 0 1 1-2.6-2.6A2.6 2.6 0 0 1 8 14.2zm7-1.9a2.6 2.6 0 1 1-2.6-2.6 2.6 2.6 0 0 1 2.6 2.6z" fill="none" stroke="currentColor" strokeWidth="1.4"/></svg>;
}

function ControlIcon({ action, playing }: { action: MediaAction; playing: boolean }) {
  if (action === "previous") return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 3v10M12.5 3.5 5.5 8l7 4.5z" fill="currentColor"/></svg>;
  if (action === "next") return <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M12 3v10M3.5 3.5l7 4.5-7 4.5z" fill="currentColor"/></svg>;
  return playing
    ? <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 3h2.8v10H4.5zm4.2 0h2.8v10H8.7z" fill="currentColor"/></svg>
    : <svg viewBox="0 0 16 16" aria-hidden="true"><path d="m5 3 7 5-7 5z" fill="currentColor"/></svg>;
}

export function NowPlayingView({
  media,
  positionSeconds = media.position_seconds,
  spectrum = null,
  busy = false,
  onControl,
}: {
  media: MediaSnapshot;
  positionSeconds?: number | null;
  spectrum?: MediaSpectrumFrame | null;
  busy?: boolean;
  onControl: (action: MediaAction) => void;
}) {
  const { t } = useI18n();
  if (!media.available || !media.player || !media.status || !["playing", "paused"].includes(media.status.toLowerCase())) return null;

  const playing = media.status.toLowerCase() === "playing";
  const progress = positionSeconds !== null && media.duration_seconds
    ? Math.min(1, Math.max(0, positionSeconds / media.duration_seconds))
    : 0;
  const title = media.title || media.identity || media.player;
  const waveform = spectrum?.bands.length
    ? spectrum.bands.map((band) => Math.max(12, Math.min(100, band * 108)))
    : progressWaveform(title, media.artist ?? "");
  const provider = mediaProvider(media.player, media.identity);
  const spectrumStyle = spectrum ? {
    "--spectrum-level": spectrum.level,
    "--spectrum-bass": spectrum.bass,
  } as CSSProperties : undefined;
  const labels: Record<MediaAction, string> = {
    previous: t("media.previous"),
    play_pause: playing ? t("media.pause") : t("media.play"),
    next: t("media.next"),
  };

  return (
    <section className={`${s.island} ${spectrum ? s.hasSpectrum : ""}`} style={spectrumStyle} data-provider={provider} aria-label={t("media.nowPlaying")}>
      <div className={s.header}>
        <span className={s.provider}><ProviderIcon provider={provider} /></span>
        <span className={s.track}>
          <span className={s.title}>{title}</span>
          <span className={s.artist}>{media.artist || media.album || media.identity}</span>
        </span>
      </div>

      <div className={s.waveform} aria-hidden="true">
        {waveform.map((height, index) => (
          <span
            key={index}
            className={index / waveform.length < progress ? s.wavePlayed : undefined}
            style={{ height: `${height}%` }}
          />
        ))}
      </div>
      <div className={s.timeline}>
        <span>{formatMediaTime(positionSeconds)}</span>
        <span>{formatMediaTime(media.duration_seconds)}</span>
      </div>

      <div className={s.controls}>
        {(["previous", "play_pause", "next"] as const).map((action) => (
          <button key={action} type="button" className={action === "play_pause" ? s.primaryControl : s.control} disabled={busy} aria-label={labels[action]} onClick={() => onControl(action)}>
            <ControlIcon action={action} playing={playing} />
          </button>
        ))}
      </div>
    </section>
  );
}

export function NowPlaying() {
  const [media, setMedia] = useState<MediaSnapshot | null>(null);
  const [positionSeconds, setPositionSeconds] = useState<number | null>(null);
  const [spectrum, setSpectrum] = useState<MediaSpectrumFrame | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(() => getMediaStatus().then(setMedia).catch(() => setMedia(null)), []);

  useEffect(() => {
    if (!isTauriRuntime()) return;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2500);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    setPositionSeconds(media?.position_seconds ?? null);
    if (!media || media.status?.toLowerCase() !== "playing" || media.position_seconds === null) return;
    const initialPosition = media.position_seconds;
    const startedAt = performance.now();
    const timer = window.setInterval(() => {
      const next = initialPosition + (performance.now() - startedAt) / 1000;
      setPositionSeconds(media.duration_seconds ? Math.min(next, media.duration_seconds) : next);
    }, 250);
    return () => window.clearInterval(timer);
  }, [media]);

  const spectrumNeeded = Boolean(media?.player && ["playing", "paused"].includes(media.status?.toLowerCase() ?? ""));
  useEffect(() => {
    if (!isTauriRuntime() || !spectrumNeeded) {
      setSpectrum(null);
      return;
    }
    let disposed = false;
    let unlisten: (() => void) | undefined;
    void listenMediaSpectrum((frame) => {
      if (!disposed) setSpectrum(frame);
    }).then((disposeListener) => {
      if (disposed) {
        disposeListener();
        return;
      }
      unlisten = disposeListener;
      return startMediaSpectrum();
    }).catch(() => setSpectrum(null));
    return () => {
      disposed = true;
      unlisten?.();
      setSpectrum(null);
      void stopMediaSpectrum().catch(() => undefined);
    };
  }, [spectrumNeeded]);

  const control = (action: MediaAction) => {
    setBusy(true);
    void controlMedia(action).then(refresh).catch(() => undefined).finally(() => setBusy(false));
  };

  return media ? <NowPlayingView media={media} positionSeconds={positionSeconds} spectrum={spectrum} busy={busy} onControl={control} /> : null;
}
