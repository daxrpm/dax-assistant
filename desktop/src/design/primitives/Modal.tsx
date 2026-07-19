import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../../lib/cn";
import { XIcon } from "../../components/icons";
import c from "./controls.module.css";
import { useI18n } from "../../i18n/I18n";

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
  const { t } = useI18n();
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const firstFocusable = dialogRef.current?.querySelector<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    (firstFocusable ?? dialogRef.current)?.focus();
    return () => {
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && onClose) {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => !element.hidden && element.getAttribute("aria-hidden") !== "true");
      if (focusable.length === 0) {
        e.preventDefault();
        dialogRef.current.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last?.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first?.focus();
      }
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
      <div
        ref={dialogRef}
        className={cn(c.modal, wide && c.modalWide)}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        aria-label={title ? undefined : t("common.actions")}
        tabIndex={-1}
      >
        {title && (
          <header className={c.modalHeader}>
            <h2 id={titleId} className={c.modalTitle}>{title}</h2>
            {onClose && (
              <button
                type="button"
                className={c.iconButton}
                onClick={onClose}
                aria-label={t("common.close")}
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
