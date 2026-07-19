import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "../i18n/I18n";
import { TitleBar } from "./WindowFrame";

describe("TitleBar", () => {
  it("exposes accurate controls and toggles maximize on title-bar double click", () => {
    const hide = vi.fn();
    const minimize = vi.fn();
    const toggle = vi.fn();
    const { container } = render(
      <I18nProvider initialLocale="en">
        <TitleBar onHide={hide} onMinimize={minimize} onToggleMaximize={toggle} />
      </I18nProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Hide Dax to tray" }));
    fireEvent.click(screen.getByRole("button", { name: "Minimize window" }));
    fireEvent.doubleClick(container.querySelector("header")!);

    expect(hide).toHaveBeenCalledOnce();
    expect(minimize).toHaveBeenCalledOnce();
    expect(toggle).toHaveBeenCalledOnce();
  });

  it("does not treat a control double click as a title-bar action", () => {
    const toggle = vi.fn();
    render(
      <I18nProvider initialLocale="es">
        <TitleBar onToggleMaximize={toggle} />
      </I18nProvider>,
    );
    fireEvent.doubleClick(screen.getByRole("button", { name: "Maximizar o restaurar ventana" }));
    expect(toggle).not.toHaveBeenCalled();
  });
});
