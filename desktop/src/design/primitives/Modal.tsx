import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../../lib/cn";
import { XIcon } from "../../components/icons";
import c from "./controls.module.css";

export interface ModalProps {
  open: boolean;
  title?: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  /** Omit to make the modal non-dismissable (the tool-confirmation case). */
  onClose?: () => void;
  children: ReactNode;
}

/**
 * Centered modal rendered in a portal.
 *
 * Escape and backdrop clicks only dismiss when `onClose` is supplied. The tool
 * confirmation modal deliberately omits it: PLAN.md 4.4 requires that the
 * request cannot be silently swallowed, since the backend fail-safe denies on
 * timeout.
 */
export function Modal({ open, title, footer, wide, onClose, children }: ModalProps) {
  useEffect(() => {
    if (!open || !onClose) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className={c.overlay}
      onMouseDown={(e) => {
        if (onClose && e.target === e.currentTarget) onClose();
      }}
    >
      <div className={cn(c.modal, wide && c.modalWide)} role="dialog" aria-modal="true">
        {title && (
          <header className={c.modalHeader}>
            <h2 className={c.modalTitle}>{title}</h2>
            {onClose && (
              <button
                type="button"
                className={c.iconButton}
                onClick={onClose}
                aria-label="Close"
              >
                <XIcon />
              </button>
            )}
          </header>
        )}
        <div className={c.modalBody}>{children}</div>
        {footer && <footer className={c.modalFooter}>{footer}</footer>}
      </div>
    </div>,
    document.body,
  );
}
