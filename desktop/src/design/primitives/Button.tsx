import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "../../lib/cn";
import s from "./primitives.module.css";
import { useI18n } from "../../i18n/I18n";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  loading?: boolean;
  children?: ReactNode;
}

export function Button({
  variant = "secondary",
  size = "md",
  fullWidth,
  loading,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cn(
        s.button,
        s[`variant-${variant}`],
        s[`size-${size}`],
        fullWidth && s.fullWidth,
        className,
      )}
      {...rest}
    >
      {loading && <Spinner size={size === "sm" ? 10 : 12} />}
      {children}
    </button>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  const { t } = useI18n();
  return (
    <span
      className={s.spinner}
      style={{ width: size, height: size }}
      role="status"
      aria-label={t("common.loading")}
    />
  );
}
