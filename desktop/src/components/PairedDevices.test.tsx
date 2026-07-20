import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../api/client";
import { I18nProvider } from "../i18n/I18n";
import { PairedDevices } from "./PairedDevices";

vi.mock("../api/client", () => ({
  api: {
    devices: vi.fn(),
    pairDevice: vi.fn(),
    revokeDevice: vi.fn(),
  },
}));

const mockApi = vi.mocked(api);

function device(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: "d1",
    name: "23129RA5FL",
    platform: "android",
    created_at: new Date().toISOString(),
    last_seen_at: null,
    revoked_at: null,
    revoked: false,
    connected: false,
    ...overrides,
  };
}

function renderPane() {
  return render(
    <I18nProvider>
      <PairedDevices />
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.devices.mockResolvedValue({ devices: [] } as never);
});

afterEach(cleanup);

describe("PairedDevices", () => {
  it("says so when nothing is paired", async () => {
    renderPane();
    expect(await screen.findByText(/no phone paired|ningún teléfono/i)).toBeTruthy();
  });

  it("shows the pairing code for transcription, spaced out", async () => {
    mockApi.pairDevice.mockResolvedValue({
      code: "ABCD2345",
      expires_in_seconds: 300,
      backend_url: "https://dax.example",
      pairing_uri: "dax://pair?url=https%3A%2F%2Fdax.example&code=ABCD2345",
    } as never);
    renderPane();

    fireEvent.click(await screen.findByRole("button"));

    // Rendered with separators so it can be read off one screen and typed
    // into another without losing place.
    expect(await screen.findByText("A B C D 2 3 4 5")).toBeTruthy();
    expect(screen.getByLabelText(/pairing qr|qr de vinculación/i)).toBeTruthy();
  });

  it("counts the code down rather than letting it expire silently", async () => {
    mockApi.pairDevice.mockResolvedValue({
      code: "ABCD2345",
      expires_in_seconds: 300,
      backend_url: "https://dax.example",
      pairing_uri: "dax://pair?url=https%3A%2F%2Fdax.example&code=ABCD2345",
    } as never);
    renderPane();

    fireEvent.click(await screen.findByRole("button"));

    expect(await screen.findByText(/300|299/)).toBeTruthy();
  });

  it("reports a paired phone that is not attached", async () => {
    mockApi.devices.mockResolvedValue({
      devices: [device({ last_seen_at: null })],
    } as never);
    renderPane();

    expect(await screen.findByText("23129RA5FL")).toBeTruthy();
    expect(await screen.findByText(/never connected|nunca/i)).toBeTruthy();
  });

  it("distinguishes a live connection from a remembered one", async () => {
    mockApi.devices.mockResolvedValue({
      devices: [device({ connected: true, last_seen_at: new Date().toISOString() })],
    } as never);
    renderPane();

    // Live presence must win over "last seen": a phone that is attached right
    // now should never read as historical.
    expect(await screen.findByText(/connected now|conectado ahora/i)).toBeTruthy();
  });

  it("hides revoked devices from the deck", async () => {
    mockApi.devices.mockResolvedValue({
      devices: [device({ revoked: true, revoked_at: new Date().toISOString() })],
    } as never);
    renderPane();

    await waitFor(() => {
      expect(screen.queryByText("23129RA5FL")).toBeNull();
    });
  });

  it("revokes and refreshes", async () => {
    mockApi.devices.mockResolvedValue({ devices: [device()] } as never);
    mockApi.revokeDevice.mockResolvedValue({ ok: true } as never);
    renderPane();

    await screen.findByText("23129RA5FL");
    const revoke = screen.getAllByRole("button").at(-1);
    if (!revoke) throw new Error("no revoke control rendered");
    fireEvent.click(revoke);

    await waitFor(() => expect(mockApi.revokeDevice).toHaveBeenCalledWith("d1"));
  });

  it("surfaces a failure to mint a code", async () => {
    mockApi.pairDevice.mockRejectedValue(new Error("nope"));
    renderPane();

    fireEvent.click(await screen.findByRole("button"));

    expect(await screen.findByText(/could not generate|no se pudo generar/i)).toBeTruthy();
  });

  it("does not surface a failed poll", async () => {
    // A banner that flickers on every network hiccup trains people to ignore
    // banners, so a failed refresh degrades to the empty state instead.
    mockApi.devices.mockRejectedValue(new Error("offline"));
    renderPane();

    expect(await screen.findByText(/no phone paired|ningún teléfono/i)).toBeTruthy();
  });
});
