import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CommandPalette } from "./CommandPalette";
import { I18nProvider } from "../i18n/I18n";

describe("CommandPalette", () => {
  it("exposes a keyboard-driven combobox and restores focus on close", () => {
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();
    const onClose = vi.fn();

    const view = render(
      <I18nProvider initialLocale="es"><CommandPalette open onClose={onClose} onNavigate={vi.fn()} /></I18nProvider>,
    );
    const input = screen.getByRole("combobox");
    const list = screen.getByRole("listbox");
    expect(document.activeElement).toBe(input);
    expect(input.getAttribute("aria-controls")).toBe(list.id);

    const initialActive = input.getAttribute("aria-activedescendant");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input.getAttribute("aria-activedescendant")).not.toBe(initialActive);
    const active = document.getElementById(input.getAttribute("aria-activedescendant")!);
    expect(active?.getAttribute("role")).toBe("option");
    expect(active?.getAttribute("aria-selected")).toBe("true");

    fireEvent.keyDown(input, { key: "Tab" });
    expect(document.activeElement).toBe(input);
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();

    view.rerender(<I18nProvider initialLocale="es"><CommandPalette open={false} onClose={onClose} onNavigate={vi.fn()} /></I18nProvider>);
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
