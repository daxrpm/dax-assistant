import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import s from "./primitives.module.css";

export type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

export function Badge({
  tone = "neutral",
  dot,
  children,
  className,
}: {
  tone?: BadgeTone;
  dot?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn(s.badge, s[`tone-${tone}`], className)}>
      {dot && <span className={s.badgeDot} />}
      {children}
    </span>
  );
}
