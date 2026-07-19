import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { ArrowDownIcon, LogsIcon, TrashIcon } from "../components/icons";
import { Badge, Button, EmptyState, Select, Toggle } from "../design/primitives";
import { LOG_BUFFER_LIMIT, useLogStream } from "../hooks/useLogStream";
import { cn } from "../lib/cn";
import { useI18n } from "../i18n/I18n";
import s from "./Logs.module.css";

const LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"];

/** Fixed row height, in px — must match `.row` in the stylesheet. */
export const ROW_HEIGHT = 22;
/** Rows rendered above and below the viewport to hide scroll tearing. */
const OVERSCAN = 12;

export function calculateVirtualWindow(
  total: number,
  scrollTop: number,
  viewportHeight: number,
  rowHeight = ROW_HEIGHT,
  overscan = OVERSCAN,
): { first: number; last: number } {
  const safeTotal = Math.max(0, total);
  const visibleStart = Math.floor(Math.max(0, scrollTop) / rowHeight);
  const visibleCount = Math.ceil(Math.max(0, viewportHeight) / rowHeight);
  return {
    first: Math.max(0, visibleStart - overscan),
    last: Math.min(safeTotal, visibleStart + visibleCount + overscan),
  };
}

function formatTime(iso: string, locale: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "--:--:--" : d.toLocaleTimeString(locale);
}

/**
 * Live log viewer.
 *
 * Virtualized by hand (PLAN.md 6.2): rows are a fixed height, so the visible
 * window is pure arithmetic and needs no measurement pass or dependency. The
 * web version renders every line, which is the memory problem this replaces —
 * combined with the 10k ring buffer in `useLogStream`, the DOM holds ~60 rows
 * no matter how much traffic passes through.
 */
export function Logs() {
  const { intlLocale, t } = useI18n();
  const { logs, connected, clear, seed } = useLogStream();
  const [level, setLevel] = useState("ALL");
  const [follow, setFollow] = useState(true);
  const [loadingSnapshot, setLoadingSnapshot] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(600);
  const viewportRef = useRef<HTMLDivElement>(null);

  // Seed from the REST snapshot so the view is populated before the first
  // socket frame arrives.
  useEffect(() => {
    let active = true;
    api
      .logs(200)
      .then((entries) => {
        if (active) seed(entries);
      })
      .catch(() => {
        // The socket will fill it in; an empty seed is not an error state.
      })
      .finally(() => {
        if (active) setLoadingSnapshot(false);
      });
    return () => {
      active = false;
    };
  }, [seed]);

  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setViewportHeight(el.clientHeight));
    observer.observe(el);
    setViewportHeight(el.clientHeight);
    return () => observer.disconnect();
  }, []);

  const filtered = useMemo(
    () => (level === "ALL" ? logs : logs.filter((l) => l.level === level)),
    [logs, level],
  );

  // Tail-follow. Depends on the row count rather than the array so it does not
  // fight the user while they are scrolled back reading.
  useEffect(() => {
    if (!follow) return;
    const el = viewportRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [filtered.length, follow]);

  const total = filtered.length;
  const { first, last } = calculateVirtualWindow(total, scrollTop, viewportHeight);
  const window = filtered.slice(first, last);

  return (
    <div className={s.logs}>
      <div className={s.bar}>
        <div className={s.barLeft}>
          <Badge tone={connected ? "success" : "danger"} dot>
            {connected ? t("logs.live") : t("common.disconnected")}
          </Badge>
          <span className={s.count}>
            {t("logs.lines", { count: total.toLocaleString(intlLocale) })}
            {logs.length >= LOG_BUFFER_LIMIT && ` ${t("logs.bufferFull")}`}
          </span>
        </div>

        <div className={s.barRight}>
          <Select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            aria-label={t("logs.filter")}
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </Select>

          <span className={s.count}>{t("logs.follow")}</span>
          <Toggle checked={follow} onChange={setFollow} aria-label={t("logs.followTail")} />

          <Button size="sm" variant="ghost" onClick={clear}>
            <TrashIcon size={13} />
            {t("logs.clear")}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              const el = viewportRef.current;
              if (el) el.scrollTop = el.scrollHeight;
            }}
          >
            <ArrowDownIcon size={13} />
            {t("logs.bottom")}
          </Button>
        </div>
      </div>

      <div
        className={s.viewport}
        ref={viewportRef}
        onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}
      >
        {total === 0 ? (
          <div className={s.emptyWrap}>
            <EmptyState
              icon={<LogsIcon size={20} />}
              title={t("logs.empty")}
              body={
                level === "ALL"
                  ? loadingSnapshot
                    ? t("logs.loading")
                    : t("logs.waiting")
                  : t("logs.nothingAt", { level })
              }
            />
          </div>
        ) : (
          <div className={s.spacer} style={{ height: total * ROW_HEIGHT }}>
            <div className={s.window} style={{ transform: `translateY(${first * ROW_HEIGHT}px)` }}>
              {window.map((entry) => (
                <div
                  key={entry.id}
                  className={cn(s.row, entry.source === "sidecar" && s.rowSidecar)}
                >
                  <span className={s.ts}>{formatTime(entry.ts, intlLocale)}</span>
                  <span className={cn(s.level, s[`level${entry.level}`])}>
                    {entry.level}
                  </span>
                  <span className={s.logger}>{entry.logger}</span>
                  <span className={s.message}>{entry.message}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
