import { type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import {
  LayoutDashboard,
  MessagesSquare,
  ScrollText,
  Settings as SettingsIcon,
  LogOut,
  Sparkles,
} from "lucide-react";
import { api } from "../api/client";
import { ThemeToggle } from "./ThemeToggle";
import { cn } from "../lib/cn";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
}

const NAV: NavItem[] = [
  { to: "/", label: "Chat", icon: <MessagesSquare size={18} />, end: true },
  { to: "/dashboard", label: "Dashboard", icon: <LayoutDashboard size={18} /> },
  { to: "/logs", label: "Logs", icon: <ScrollText size={18} /> },
  { to: "/settings", label: "Settings", icon: <SettingsIcon size={18} /> },
];

const TITLES: Record<string, string> = {
  "/": "Chat",
  "/dashboard": "Dashboard",
  "/logs": "Logs",
  "/settings": "Settings",
};

export function AppShell({ authEnabled }: { authEnabled: boolean }) {
  const location = useLocation();
  const title = TITLES[location.pathname] ?? "Dax";

  const logout = async () => {
    await api.logout().catch(() => undefined);
    window.location.reload();
  };

  return (
    <div className="flex h-full bg-background text-foreground">
      {/* Sidebar */}
      <aside className="flex w-60 shrink-0 flex-col border-r border-separator bg-surface">
        <div className="flex items-center gap-2 px-5 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent text-accent-foreground">
            <Sparkles size={18} />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold">Dax</p>
            <p className="text-xs text-muted">Assistant</p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1 px-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent-soft text-accent-soft-foreground"
                    : "text-muted hover:bg-surface-secondary hover:text-foreground",
                )
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        {authEnabled && (
          <div className="px-3 pb-4">
            <button
              type="button"
              onClick={logout}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-danger-soft hover:text-danger-soft-foreground"
            >
              <LogOut size={18} />
              Log out
            </button>
          </div>
        )}
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-separator px-6">
          <h1 className="text-lg font-semibold">{title}</h1>
          <ThemeToggle />
        </header>
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
