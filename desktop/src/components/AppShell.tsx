import type { ReactNode } from "react";
import { cn } from "../lib/cn";
import type { ThemeMode } from "../lib/useTheme";
import { Button } from "../design/primitives";
import {
  ChatIcon,
  DashboardIcon,
  LogsIcon,
  McpIcon,
  SettingsIcon,
  StoreIcon,
  TerminalIcon,
} from "./icons";
import s from "./AppShell.module.css";

export interface NavEntry {
  route: string;
  label: string;
  icon: ReactNode;
  /** Screens not yet built in this milestone render a placeholder. */
  ready: boolean;
}

export const NAV: NavEntry[] = [
  { route: "/chat", label: "Chat", icon: <ChatIcon />, ready: true },
  { route: "/dashboard", label: "Dashboard", icon: <DashboardIcon />, ready: true },
  { route: "/mcp", label: "MCP", icon: <McpIcon />, ready: true },
  { route: "/marketplace", label: "Marketplace", icon: <StoreIcon />, ready: true },
  { route: "/commands", label: "Commands", icon: <TerminalIcon />, ready: true },
  { route: "/logs", label: "Logs", icon: <LogsIcon />, ready: true },
  { route: "/settings", label: "Settings", icon: <SettingsIcon />, ready: true },
];

const THEME_LABEL: Record<ThemeMode, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

const THEME_ORDER: ThemeMode[] = ["system", "light", "dark"];

export function AppShell({
  route,
  onNavigate,
  themeMode,
  onCycleTheme,
  onLogout,
  bare,
  children,
}: {
  route: string;
  onNavigate: (route: string) => void;
  themeMode: ThemeMode;
  onCycleTheme: (next: ThemeMode) => void;
  onLogout: () => void;
  /** Skip the padded scroll wrapper for screens that manage their own layout. */
  bare?: boolean;
  children: ReactNode;
}) {
  const nextTheme =
    THEME_ORDER[(THEME_ORDER.indexOf(themeMode) + 1) % THEME_ORDER.length] ?? "system";

  return (
    <div className={s.shell}>
      <aside className={s.sidebar}>
        <div className={s.sidebarHeader}>
          <span className={s.wordmark}>Dax</span>
        </div>

        <nav className={s.nav}>
          <div className={s.groupHeader}>Workspace</div>
          {NAV.map((entry) => (
            <button
              key={entry.route}
              type="button"
              onClick={() => onNavigate(entry.route)}
              aria-current={route === entry.route ? "page" : undefined}
              className={cn(s.navItem, route === entry.route && s.navItemSelected)}
            >
              <span className={s.navIcon}>{entry.icon}</span>
              {entry.label}
            </button>
          ))}
        </nav>

        <div className={s.sidebarFooter}>
          <Button size="sm" variant="ghost" onClick={() => onCycleTheme(nextTheme)}>
            {THEME_LABEL[themeMode]}
          </Button>
          <Button size="sm" variant="ghost" onClick={onLogout}>
            Sign out
          </Button>
        </div>
      </aside>

      <main className={s.content}>
        {/*
          Full-bleed screens (Chat, Logs, Settings) own their own scrolling and
          internal chrome, so they skip the padded scroll wrapper entirely.
        */}
        {bare ? children : <div className={s.contentScroll}>{children}</div>}
      </main>
    </div>
  );
}
