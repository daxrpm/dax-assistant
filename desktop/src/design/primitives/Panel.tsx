import type { ReactNode } from "react";
import { cn } from "../../lib/cn";
import s from "./primitives.module.css";

export function Panel({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <section className={cn(s.panel, className)}>{children}</section>;
}

export function PanelHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className={s.panelHeader}>
      <div>
        <h2 className={s.panelTitle}>{title}</h2>
        {subtitle && <div className={s.panelSubtitle}>{subtitle}</div>}
      </div>
      {actions}
    </header>
  );
}

export function PanelBody({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return <div className={cn(s.panelBody, className)}>{children}</div>;
}
