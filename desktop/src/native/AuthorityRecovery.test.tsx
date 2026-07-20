import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";

const { recover, shutdown } = vi.hoisted(() => ({ recover: vi.fn(), shutdown: vi.fn() }));

vi.mock("../api/connection", () => ({
  getConnectionSettings: () => ({
    active_url: "https://dax.example",
    active_server_id: "old-authority",
  }),
  isTauri: () => true,
  recoverSameOriginAuthorityReplacement: recover,
}));
vi.mock("../stores/realtime", () => ({ shutdownRealtimeStores: shutdown }));

import { I18nProvider } from "../i18n/I18n";
import { AuthorityRecovery } from "./AuthorityRecovery";

describe("AuthorityRecovery", () => {
  beforeEach(() => {
    recover.mockReset();
    shutdown.mockReset();
  });
  afterEach(cleanup);

  it("requires destructive confirmation before replacing an authority", async () => {
    const onRecovered = vi.fn();
    recover.mockResolvedValue({ healthy: true });
    render(<I18nProvider initialLocale="en"><AuthorityRecovery onRecovered={onRecovered} /></I18nProvider>);

    expect(recover).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Replace authority at this origin" }));
    expect(screen.getByRole("dialog", { name: "Confirm authority replacement" })).toBeTruthy();
    expect(screen.getByText("old-authority")).toBeTruthy();
    expect(recover).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Clear identity and credentials" }));
    await waitFor(() => expect(recover).toHaveBeenCalledOnce());
    expect(shutdown).toHaveBeenCalledOnce();
    expect(onRecovered).toHaveBeenCalledOnce();
  });

  it("does not continue when health resolution fails", async () => {
    const onRecovered = vi.fn();
    recover.mockResolvedValue({ healthy: false });
    render(<I18nProvider initialLocale="en"><AuthorityRecovery onRecovered={onRecovered} /></I18nProvider>);

    fireEvent.click(screen.getByRole("button", { name: "Replace authority at this origin" }));
    fireEvent.click(screen.getByRole("button", { name: "Clear identity and credentials" }));

    expect((await screen.findByRole("alert")).textContent).toContain("still unreachable");
    expect(onRecovered).not.toHaveBeenCalled();
  });
});
