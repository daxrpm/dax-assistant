import {
  createContext,
  useContext,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import {
  Card as HeroCard,
  Chip as HeroChip,
  Input as HeroInput,
  Modal as HeroModal,
  Switch as HeroSwitch,
  TextArea as HeroTextArea,
} from "@heroui/react";
import { cn } from "../lib/cn";

/* ── Panel / Card ──────────────────────────────────────────────────────── */

export function Panel({
  children,
  className,
  ...rest
}: { children: ReactNode; className?: string } & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <HeroCard
      className={cn("p-5", className)}
      {...rest}
    >
      {children}
    </HeroCard>
  );
}

export function PanelHeader({
  title,
  description,
  action,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-base font-semibold leading-tight">{title}</h2>
        {description && (
          <p className="mt-0.5 text-sm text-muted">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/* ── Badge / Chip ──────────────────────────────────────────────────────── */

type BadgeColor = "default" | "accent" | "success" | "warning" | "danger";

export function Badge({
  children,
  color = "default",
  className,
}: {
  children: ReactNode;
  color?: BadgeColor;
  className?: string;
}) {
  const colorMap: Record<BadgeColor, "default" | "accent" | "success" | "warning" | "danger"> = {
    default: "default",
    accent: "accent",
    success: "success",
    warning: "warning",
    danger: "danger",
  };
  return (
    <HeroChip size="sm" color={colorMap[color]} variant="soft" className={className}>
      {children}
    </HeroChip>
  );
}

/* ── Form field wrapper ────────────────────────────────────────────────── */

export function Field({
  label,
  description,
  children,
  htmlFor,
}: {
  label: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-sm font-medium">
        {label}
      </label>
      {children}
      {description && <p className="text-xs text-muted">{description}</p>}
    </div>
  );
}

const FIELD_BASE =
  "w-full rounded-xl border border-separator bg-background px-3 py-2 text-sm " +
  "outline-none transition-colors placeholder:text-muted " +
  "focus:border-accent focus:ring-2 focus:ring-accent/30 disabled:opacity-60";

export function TextInput(props: InputHTMLAttributes<HTMLInputElement>) {
  return <HeroInput {...props} fullWidth className={props.className} />;
}

export function TextArea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <HeroTextArea {...props} fullWidth className={props.className} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={cn(FIELD_BASE, "appearance-none cursor-pointer pr-8", props.className)}
    />
  );
}

/* ── Toggle (accessible switch) ────────────────────────────────────────── */

export function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string;
}) {
  return (
    <HeroSwitch
      isSelected={checked}
      aria-label={label}
      isDisabled={disabled}
      onChange={onChange}
    />
  );
}

/* ── Tabs (controlled, simple) ─────────────────────────────────────────── */

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: ReactNode; icon?: ReactNode }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-xl border border-separator bg-surface p-1 scroll-slim">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={cn(
            "flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
            active === t.id
              ? "bg-accent text-accent-foreground"
              : "text-muted hover:bg-surface-secondary hover:text-foreground",
          )}
        >
          {t.icon}
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ── Modal ─────────────────────────────────────────────────────────────── */

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
}: {
  open: boolean;
  onClose?: () => void;
  title?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}) {
  if (!open) return null;
  return (
    <HeroModal isOpen={open} onOpenChange={(next) => !next && onClose?.()}>
      <HeroModal.Backdrop>
        <HeroModal.Container size="lg" scroll="inside">
          <HeroModal.Dialog>
            {title && (
              <HeroModal.Header>
                <HeroModal.Heading>{title}</HeroModal.Heading>
              </HeroModal.Header>
            )}
            <HeroModal.Body>{children}</HeroModal.Body>
            {footer && <HeroModal.Footer>{footer}</HeroModal.Footer>}
          </HeroModal.Dialog>
        </HeroModal.Container>
      </HeroModal.Backdrop>
    </HeroModal>
  );
}

/* ── Toast ─────────────────────────────────────────────────────────────── */

type Toast = { id: number; message: string; color: BadgeColor };
type ToastCtx = { show: (message: string, color?: BadgeColor) => void };

const ToastContext = createContext<ToastCtx | null>(null);

export function useToast(): ToastCtx {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}

export { ToastContext };
export type { Toast, BadgeColor };
