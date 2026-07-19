import type { ReactNode } from "react";
import type { ThemeMode } from "../lib/useTheme";
import { Button } from "../design/primitives";
import { PALETTE_ROUTES } from "./CommandPalette";
import { useI18n } from "../i18n/I18n";
import s from "./AppShell.module.css";
import { AppIcon } from "./AppIcon";

/**
 * The chrome for a *summoned* screen.
 *
 * PLAN.md 5.0 removed the sidebar: Chat, MCP, Marketplace, Comandos, Registro
 * and Ajustes are palette destinations now, not permanent nav, so the shell no
 * longer spends 218px on links used once a day. What remains is a strip that
 * answers two questions — where am I, and how do I get back to the deck — plus
 * the two account-level verbs that have nowhere better to live.
 *
 * The deck itself does not use this shell; it renders full-window.
 */
const THEME_ORDER: ThemeMode[] = ["system", "light", "dark"];

export function AppShell({
  route,
  onNavigate,
  onOpenPalette,
  themeMode,
  onCycleTheme,
  onLogout,
  bare,
  children,
}: {
  route: string;
  onNavigate: (route: string) => void;
  onOpenPalette: () => void;
  themeMode: ThemeMode;
  onCycleTheme: (next: ThemeMode) => void;
  onLogout: () => void;
  /** Skip the padded scroll wrapper for screens that manage their own layout. */
  bare?: boolean;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const nextTheme =
    THEME_ORDER[(THEME_ORDER.indexOf(themeMode) + 1) % THEME_ORDER.length] ?? "system";
  const current = PALETTE_ROUTES.find((entry) => entry.route === route);

  return (
    <div className={s.shell}>
      <header className={s.strip}>
        <button
          type="button"
          className={s.back}
          onClick={() => onNavigate("/")}
          aria-label={t("shell.back")}
        >
          <span className={s.backArrow}>←</span>
          <AppIcon size={21} className={s.appIcon} />
          <span className={s.wordmark}>Dax</span>
        </button>

        <span className={s.crumb}>{current ? t(current.labelKey) : route}</span>

        <div className={s.stripActions}>
          <button type="button" className={s.paletteHint} onClick={onOpenPalette}>
            <kbd className={s.kbd}>⌘K</kbd>
            <span>{t("shell.commands")}</span>
          </button>
          <Button size="sm" variant="ghost" onClick={() => onCycleTheme(nextTheme)}>
            {t(themeMode === "light" ? "theme.light" : themeMode === "dark" ? "theme.dark" : "theme.system")}
          </Button>
          <Button size="sm" variant="ghost" onClick={onLogout}>
            {t("palette.logout")}
          </Button>
        </div>
      </header>

      <main className={s.content}>
        {/*
          Full-bleed screens (Chat, Registro, Ajustes) own their own scrolling
          and internal chrome, so they skip the padded scroll wrapper entirely.
        */}
        {bare ? children : <div className={s.contentScroll}>{children}</div>}
      </main>
    </div>
  );
}
