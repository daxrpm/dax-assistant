import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18n";
import type { MediaSnapshot } from "../native/media";
import { formatMediaTime, mediaProvider, NowPlayingView, progressWaveform } from "./NowPlaying";

const media: MediaSnapshot = {
  available: true,
  player: "spotify",
  identity: "Spotify",
  status: "Playing",
  title: "Northern Lights",
  artist: "Dax Quartet",
  album: "Night Shift",
  position_seconds: 30,
  duration_seconds: 120,
};

afterEach(cleanup);

describe("NowPlaying", () => {
  it("maps known MPRIS players to local provider treatments", () => {
    expect(mediaProvider("spotify")).toBe("spotify");
    expect(mediaProvider("firefox.instance_1")).toBe("browser");
    expect(mediaProvider("org.mpris.MediaPlayer2.vlc")).toBe("generic");
  });

  it("renders track details, progress and fixed controls", () => {
    const control = vi.fn();
    const view = render(<I18nProvider initialLocale="en"><NowPlayingView media={media} onControl={control} /></I18nProvider>);
    expect(screen.getByLabelText("Now playing")).toBeTruthy();
    expect(screen.getByText("Northern Lights")).toBeTruthy();
    expect(screen.getByText("Dax Quartet")).toBeTruthy();
    expect(view.container.querySelectorAll("[aria-hidden='true'] > span")).toHaveLength(
      progressWaveform("Northern Lights", "Dax Quartet").length,
    );
    expect(view.container.querySelectorAll("[aria-hidden='true'] > span[class]")).toHaveLength(
      Math.ceil(progressWaveform("Northern Lights", "Dax Quartet").length * 0.25),
    );
    expect(screen.getByText("0:30")).toBeTruthy();
    expect(screen.getByText("2:00")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("Next"));
    expect(control).toHaveBeenCalledWith("next");
  });

  it("builds a stable bounded waveform and formats time", () => {
    const first = progressWaveform("Northern Lights", "Dax Quartet");
    expect(first).toEqual(progressWaveform("Northern Lights", "Dax Quartet"));
    expect(first.length).toBeGreaterThanOrEqual(32);
    expect(first.length).toBeLessThanOrEqual(48);
    expect(progressWaveform("Another Song", "Dax Quartet")).not.toEqual(first);
    expect(formatMediaTime(65.9)).toBe("1:05");
    expect(formatMediaTime(null)).toBe("--:--");
  });

  it("renders native spectrum bands while retaining track progress", () => {
    const spectrum = { bands: [0.1, 0.5, 0.9], bass: 0.4, level: 0.6 };
    const view = render(
      <I18nProvider initialLocale="en">
        <NowPlayingView media={media} positionSeconds={60} spectrum={spectrum} onControl={vi.fn()} />
      </I18nProvider>,
    );
    const bars = view.container.querySelectorAll("[aria-hidden='true'] > span");
    expect(bars).toHaveLength(3);
    expect(bars.item(1).getAttribute("style")).toContain("54%");
    expect(screen.getByText("1:00")).toBeTruthy();
  });

  it("stays hidden when playerctl or playback is unavailable", () => {
    const hidden = { ...media, available: false };
    const { container } = render(<I18nProvider><NowPlayingView media={hidden} onControl={vi.fn()} /></I18nProvider>);
    expect(container.childElementCount).toBe(0);
  });
});
