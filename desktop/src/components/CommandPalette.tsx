import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "../lib/cn";
import { useI18n } from "../i18n/I18n";
import {
  ChatIcon,
  DashboardIcon,
  LogsIcon,
  McpIcon,
  SearchIcon,
  SettingsIcon,
  StoreIcon,
  TerminalIcon,
  VoiceIcon,
} from "./icons";
import s from "./CommandPalette.module.css";

/**
 * The ⌘K palette.
 *
 * PLAN.md 5.0 makes this structural rather than cosmetic: Chat, MCP,
 * Marketplace, Comandos, Logs and Ajustes stop being permanent menu
 * destinations and are summoned from here, which is what freed the 218px the
 * sidebar spent on links used once a day.
 *
 * Keyboard-first throughout — the list is driven by ↑/↓/Enter and the mouse is
 * never required to reach anything.
 */

export interface PaletteAction {
  id: string;
  label: string;
  /** Machine-side hint: route, shortcut, or current value. */
  hint?: string;
  group: string;
  icon?: React.ReactNode;
  run: () => void;
}

export interface PaletteRoute {
  route: string;
  label: string;
  icon: React.ReactNode;
}

export const PALETTE_ROUTES = [
  { route: "/", labelKey: "route.deck", icon: <DashboardIcon /> },
  { route: "/chat", labelKey: "route.chat", icon: <ChatIcon /> },
  { route: "/mcp", labelKey: "route.mcp", icon: <McpIcon /> },
  { route: "/marketplace", labelKey: "route.marketplace", icon: <StoreIcon /> },
  { route: "/commands", labelKey: "route.commands", icon: <TerminalIcon /> },
  { route: "/logs", labelKey: "route.logs", icon: <LogsIcon /> },
  { route: "/settings", labelKey: "route.settings", icon: <SettingsIcon /> },
] as const;

/** Case- and accent-insensitive substring match, so "sesion" finds "sesión". */
function fold(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function CommandPalette({
  open,
  onClose,
  onNavigate,
  extraActions = [],
}: {
  open: boolean;
  onClose: () => void;
  onNavigate: (route: string) => void;
  /** Verbs contributed by the shell — voice toggle, theme, sign out. */
  extraActions?: PaletteAction[];
}) {
  const { t } = useI18n();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const listId = "command-palette-listbox";

  const actions = useMemo<PaletteAction[]>(
    () => [
      ...PALETTE_ROUTES.map((entry) => ({
        id: `nav:${entry.route}`,
        label: t(entry.labelKey),
        hint: entry.route,
        group: t("palette.goTo"),
        icon: entry.icon,
        run: () => onNavigate(entry.route),
      })),
      ...extraActions,
    ],
    [extraActions, onNavigate, t],
  );

  const results = useMemo(() => {
    const q = fold(query.trim());
    if (!q) return actions;
    return actions.filter(
      (action) => fold(action.label).includes(q) || fold(action.hint ?? "").includes(q),
    );
  }, [actions, query]);

  // Reopening always starts clean; a stale query from last time is a surprise.
  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement | null;
    setQuery("");
    setCursor(0);
    inputRef.current?.focus();
    return () => {
      if (previousFocus.current?.isConnected) previousFocus.current.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'input:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.tabIndex >= 0 && !element.hidden);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    setCursor((prev) => Math.min(prev, Math.max(0, results.length - 1)));
  }, [results.length]);

  // Keep the highlighted row in view when driving the list from the keyboard.
  useEffect(() => {
    const active = listRef.current?.querySelector<HTMLElement>(`[data-index="${cursor}"]`);
    if (typeof active?.scrollIntoView === "function") {
      active.scrollIntoView({ block: "nearest" });
    }
  }, [cursor]);

  const commit = useCallback(
    (action: PaletteAction | undefined) => {
      if (!action) return;
      onClose();
      action.run();
    },
    [onClose],
  );

  if (!open) return null;

  const grouped: { group: string; items: { action: PaletteAction; index: number }[] }[] =
    [];
  results.forEach((action, index) => {
    const bucket = grouped.find((g) => g.group === action.group);
    if (bucket) bucket.items.push({ action, index });
    else grouped.push({ group: action.group, items: [{ action, index }] });
  });

  return createPortal(
    <div
      className={s.overlay}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className={s.palette}
        role="dialog"
        aria-modal="true"
        aria-label={t("palette.commands")}
      >
        <div className={s.searchRow}>
          <span className={s.searchIcon}>
            <SearchIcon />
          </span>
          <input
            ref={inputRef}
            className={s.input}
            value={query}
            placeholder={t("palette.search")}
            spellCheck={false}
            role="combobox"
            aria-autocomplete="list"
            aria-expanded="true"
            aria-controls={listId}
            aria-activedescendant={results[cursor] ? `command-${results[cursor].id}` : undefined}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setCursor((c) => (results.length ? (c + 1) % results.length : 0));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setCursor((c) =>
                  results.length ? (c - 1 + results.length) % results.length : 0,
                );
              } else if (e.key === "Enter") {
                e.preventDefault();
                commit(results[cursor]);
              }
            }}
          />
          <kbd className={s.kbd}>esc</kbd>
        </div>

        <div
          id={listId}
          className={s.list}
          ref={listRef}
          role="listbox"
          aria-label={t("palette.results")}
        >
          {results.length === 0 ? (
            <div className={s.empty}>{t("common.noResults")}</div>
          ) : (
            grouped.map((bucket) => (
              <div key={bucket.group} role="group" aria-label={bucket.group}>
                <div className={s.groupLabel} aria-hidden="true">{bucket.group}</div>
                {bucket.items.map(({ action, index }) => (
                  <button
                    key={action.id}
                    type="button"
                    id={`command-${action.id}`}
                    role="option"
                    aria-selected={index === cursor}
                    tabIndex={-1}
                    data-index={index}
                    className={cn(s.row, index === cursor && s.rowActive)}
                    onMouseMove={() => setCursor(index)}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => commit(action)}
                  >
                    <span className={s.rowIcon}>{action.icon ?? <VoiceIcon />}</span>
                    <span className={s.rowLabel}>{action.label}</span>
                    {action.hint && <span className={s.rowHint}>{action.hint}</span>}
                  </button>
                ))}
              </div>
            ))
          )}
        </div>

        <div className={s.footer}>
          <span>
            <kbd className={s.kbd}>↑</kbd>
            <kbd className={s.kbd}>↓</kbd> {t("palette.navigate")}
          </span>
          <span>
            <kbd className={s.kbd}>↵</kbd> {t("palette.open")}
          </span>
        </div>
      </div>
    </div>,
    document.body,
  );
}

/**
 * Global ⌘K / Ctrl+K binding.
 *
 * Deliberately ignores the shortcut while a text field has focus only for the
 * *plain* form — with a modifier held the user means the palette, wherever the
 * caret happens to be.
 */
export function usePaletteShortcut(toggle: () => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle]);
}
