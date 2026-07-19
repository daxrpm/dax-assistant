import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";
import { I18nProvider } from "../../i18n/I18n";

describe("Modal", () => {
  it("labels the dialog, traps focus, closes on Escape, and restores focus", () => {
    const onClose = vi.fn();
    const trigger = document.createElement("button");
    document.body.append(trigger);
    trigger.focus();

    const view = render(
      <I18nProvider initialLocale="en"><Modal open title="Confirm action" footer={<button>Allow</button>} onClose={onClose}>
        <input aria-label="Reason" />
      </Modal></I18nProvider>,
    );

    const dialog = screen.getByRole("dialog", { name: "Confirm action" });
    const close = screen.getByRole("button", { name: "Close" });
    const allow = screen.getByRole("button", { name: "Allow" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(document.activeElement).toBe(close);

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(allow);
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();

    view.rerender(<I18nProvider initialLocale="en"><Modal open={false} title="Confirm action" onClose={onClose}>Body</Modal></I18nProvider>);
    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });
});
