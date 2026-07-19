import { useId, type ReactNode } from "react";
import { cn } from "../../lib/cn";
import s from "./primitives.module.css";

export interface FieldProps {
  label?: ReactNode;
  description?: ReactNode;
  error?: ReactNode;
  className?: string;
  /** Receives the generated id so the control can be labelled correctly. */
  children: (id: string) => ReactNode;
}

/**
 * Label + description + control + error, wired for accessibility.
 *
 * The render-prop shape exists so the generated id reaches the control without
 * the caller having to invent one.
 */
export function Field({ label, description, error, className, children }: FieldProps) {
  const id = useId();
  return (
    <div className={cn(s.field, className)}>
      {label && (
        <label className={s.fieldLabel} htmlFor={id}>
          {label}
        </label>
      )}
      {children(id)}
      {description && !error && <div className={s.fieldDescription}>{description}</div>}
      {error && (
        <div className={s.fieldError} role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
