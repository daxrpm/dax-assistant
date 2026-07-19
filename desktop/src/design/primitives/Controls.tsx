import {
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "../../lib/cn";
import { CheckIcon } from "../../components/icons";
import c from "./controls.module.css";

/* ---------------- IconButton ---------------- */

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  danger?: boolean;
}

export function IconButton({
  label,
  danger,
  className,
  children,
  ...rest
}: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(c.iconButton, danger && c.iconButtonDanger, className)}
      {...rest}
    >
      {children}
    </button>
  );
}

/* ---------------- Tabs ---------------- */

export interface TabItem<T extends string = string> {
  id: T;
  label: ReactNode;
}

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (next: T) => void;
  className?: string;
}) {
  return (
    <div className={cn(c.tabList, className)} role="tablist">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="tab"
          aria-selected={item.id === value}
          className={cn(c.tab, item.id === value && c.tabSelected)}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- SegmentedControl ---------------- */

export function SegmentedControl<T extends string>({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (next: T) => void;
  className?: string;
}) {
  return (
    <div className={cn(c.segmented, className)} role="radiogroup">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          role="radio"
          aria-checked={item.id === value}
          className={cn(c.segment, item.id === value && c.segmentSelected)}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

/* ---------------- Slider ---------------- */

export function Slider({
  value,
  onChange,
  min = 0,
  max = 1,
  step = 0.01,
  disabled,
  id,
  format,
}: {
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  id?: string;
  /** Renders the trailing readout. Defaults to the raw number. */
  format?: (value: number) => string;
}) {
  return (
    <div className={c.sliderRow}>
      <input
        id={id}
        type="range"
        className={c.slider}
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <span className={c.sliderValue}>{format ? format(value) : String(value)}</span>
    </div>
  );
}

/* ---------------- Checkbox ---------------- */

export function Checkbox({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label?: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className={c.checkboxRow}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        style={{ position: "absolute", opacity: 0, width: 0, height: 0 }}
      />
      <span className={cn(c.checkbox, checked && c.checkboxOn)} aria-hidden="true">
        {checked && <CheckIcon size={11} />}
      </span>
      {label && <span className={c.checkboxLabel}>{label}</span>}
    </label>
  );
}

/* ---------------- List ---------------- */

export function List({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn(c.list, className)}>{children}</div>;
}

export function ListRow({
  selected,
  onClick,
  className,
  children,
}: {
  selected?: boolean;
  onClick?: () => void;
  className?: string;
  children: ReactNode;
}) {
  const classes = cn(
    c.listRow,
    onClick && c.listRowInteractive,
    selected && c.listRowSelected,
    className,
  );
  if (!onClick) return <div className={classes}>{children}</div>;
  return (
    <button type="button" className={classes} onClick={onClick}>
      {children}
    </button>
  );
}

/* ---------------- EmptyState ---------------- */

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon?: ReactNode;
  title: ReactNode;
  body?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className={c.empty}>
      {icon && <div className={c.emptyIcon}>{icon}</div>}
      <div className={c.emptyTitle}>{title}</div>
      {body && <div className={c.emptyBody}>{body}</div>}
      {action}
    </div>
  );
}

/* ---------------- CodeBlock ---------------- */

export function CodeBlock({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <pre className={cn(c.code, "selectable", className)}>{children}</pre>;
}

/* ---------------- Separator ---------------- */

export function Separator({ className }: { className?: string }) {
  return <hr className={cn(c.separator, className)} />;
}

/* ---------------- Tooltip ---------------- */

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className={c.tooltipWrap}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <span className={c.tooltip} role="tooltip">
          {label}
        </span>
      )}
    </span>
  );
}

/* ---------------- Popover ---------------- */

export type PopoverPlacement = "top" | "bottom" | "bottom-end";

/**
 * Anchored overlay that closes on outside mousedown or Escape.
 *
 * Positioned with plain CSS rather than a floating-element library: every use
 * here is anchored to a control whose available space is known, and pulling in
 * a positioning engine for that is not worth the bytes.
 */
export function Popover({
  open,
  onClose,
  trigger,
  placement = "bottom",
  children,
}: {
  open: boolean;
  onClose: () => void;
  trigger: ReactNode;
  placement?: PopoverPlacement;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  const placementClass =
    placement === "top"
      ? c.popoverTop
      : placement === "bottom-end"
        ? c.popoverBottomEnd
        : c.popoverBottom;

  return (
    <div className={c.popoverWrap} ref={ref}>
      {trigger}
      {open && <div className={cn(c.popover, placementClass)}>{children}</div>}
    </div>
  );
}
