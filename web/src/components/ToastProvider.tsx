import { useCallback, useRef, useState, type ReactNode } from "react";
import { CheckCircle2, AlertTriangle, Info, XCircle } from "lucide-react";
import { ToastContext, type BadgeColor, type Toast } from "./ui";
import { cn } from "../lib/cn";

const ICONS: Record<BadgeColor, ReactNode> = {
  default: <Info size={16} />,
  accent: <Info size={16} />,
  success: <CheckCircle2 size={16} />,
  warning: <AlertTriangle size={16} />,
  danger: <XCircle size={16} />,
};

const COLORS: Record<BadgeColor, string> = {
  default: "border-separator bg-surface",
  accent: "border-accent/40 bg-surface",
  success: "border-success/40 bg-surface",
  warning: "border-warning/40 bg-surface",
  danger: "border-danger/40 bg-surface",
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const counter = useRef(0);

  const show = useCallback((message: string, color: BadgeColor = "default") => {
    const id = ++counter.current;
    setToasts((prev) => [...prev, { id, message, color }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto flex items-center gap-2 rounded-xl border px-4 py-3 text-sm shadow-lg",
              COLORS[t.color],
            )}
          >
            <span
              className={cn(
                t.color === "success" && "text-success",
                t.color === "danger" && "text-danger",
                t.color === "warning" && "text-warning",
                (t.color === "accent" || t.color === "default") && "text-accent",
              )}
            >
              {ICONS[t.color]}
            </span>
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
