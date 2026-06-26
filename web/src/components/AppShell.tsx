import { type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import {
  LayoutDashboard,
  MessagesSquare,
  ScrollText,
  Settings as SettingsIcon,
  LogOut,
  Sparkles,
  Server,
  Terminal,
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
  { to: "/mcp", label: "MCP", icon: <Server size={18} /> },
  { to: "/shell", label: "Commands", icon: <Terminal size={18} /> },
  { to: "/logs", label: "Logs", icon: <ScrollText size={18} /> },
  { to: "/settings", label: "Settings", icon: <SettingsIcon size={18} /> },
];

const TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/mcp": "MCP Servers",
  "/shell": "Shell Commands",
  "/logs": "Logs",
  "/settings": "Settings",
};

export function AppShell({ authEnabled }: { authEnabled: boolean }) {
  const location = useLocation();
  const isChat =
    location.pathname === "/" || location.pathname.startsWith("/c/");
  const title = TITLES[location.pathname] ?? "Dax";

  const logout = async () => {
    await api.logout().catch(() => undefined);
    window.location.reload();
  };

  // On the chat route, collapse the nav sidebar to icons-only to save horizontal space.
  const sidebarWidth = isChat ? "w-14" : "w-60";

  return (
    <div className="flex h-full bg-background text-foreground">
      {/* Nav sidebar — narrow on chat route, full on others */}
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r border-separator bg-surface transition-all",
          sidebarWidth,
        )}
      >
        <div className={cn("flex items-center py-4", isChat ? "justify-center px-0" : "gap-2 px-5")}>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
            <Sparkles size={18} />
          </div>
          {!isChat && (
            <div className="leading-tight">
              <p className="text-sm font-semibold">Dax</p>
              <p className="text-xs text-muted">Assistant</p>
            </div>
          )}
        </div>

        <nav className={cn("flex flex-1 flex-col gap-1", isChat ? "items-center px-1" : "px-3")}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={isChat ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  "flex items-center rounded-xl transition-colors",
                  isChat
                    ? "h-10 w-10 justify-center"
                    : "gap-3 px-3 py-2 text-sm font-medium",
                  isActive
                    ? "bg-accent-soft text-accent-soft-foreground"
                    : "text-muted hover:bg-surface-secondary hover:text-foreground",
                )
              }
            >
              {item.icon}
              {!isChat && item.label}
            </NavLink>
          ))}
        </nav>

        {authEnabled && (
          <div className={cn("pb-4", isChat ? "flex justify-center px-0" : "px-3")}>
            <button
              type="button"
              onClick={logout}
              title={isChat ? "Log out" : undefined}
              className={cn(
                "flex items-center rounded-xl text-muted transition-colors hover:bg-danger-soft hover:text-danger-soft-foreground",
                isChat ? "h-10 w-10 justify-center" : "w-full gap-3 px-3 py-2 text-sm font-medium",
              )}
            >
              <LogOut size={18} />
              {!isChat && "Log out"}
            </button>
          </div>
        )}
      </aside>

      {/* Main content */}
      <div className="flex min-w-0 flex-1 flex-col">
        {!isChat && (
          <header className="flex h-16 shrink-0 items-center justify-between border-b border-separator px-6">
            <h1 className="text-lg font-semibold">{title}</h1>
            <ThemeToggle />
          </header>
        )}
        <main className="min-h-0 flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
