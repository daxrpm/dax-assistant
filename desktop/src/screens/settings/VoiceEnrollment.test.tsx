import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import { ToastProvider } from "../../design/primitives";
import { I18nProvider } from "../../i18n/I18n";
import { VoiceEnrollment } from "./VoiceEnrollment";

describe("VoiceEnrollment", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("stops a permission stream that resolves after unmount", async () => {
    vi.spyOn(api, "voiceProfile").mockResolvedValue({ enrolled: false });
    let resolvePermission!: (stream: MediaStream) => void;
    const permission = new Promise<MediaStream>((resolve) => {
      resolvePermission = resolve;
    });
    const stop = vi.fn();
    vi.stubGlobal("navigator", {
      languages: ["en"],
      language: "en",
      mediaDevices: { getUserMedia: vi.fn(() => permission) },
    });
    const view = render(
      <I18nProvider initialLocale="en">
        <ToastProvider>
          <VoiceEnrollment />
        </ToastProvider>
      </I18nProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Record sample" }));
    view.unmount();

    resolvePermission({ getTracks: () => [{ stop }] } as unknown as MediaStream);
    await permission;
    await vi.waitFor(() => expect(stop).toHaveBeenCalledOnce());
  });
});
