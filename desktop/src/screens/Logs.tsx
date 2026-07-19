import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import { ArrowDownIcon, LogsIcon, TrashIcon } from "../components/icons";
import { Badge, Button, EmptyState, Select, Toggle } from "../design/primitives";
import { LOG_BUFFER_LIMIT, useLogStream } from "../hooks/useLogStream";
import { cn } from "../lib/cn";
import s from "./Logs.module.css";

const LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"];

/** Fixed row height, in px — must match `.row` in the stylesheet. */
const ROW_HEIGHT = 18;
/** Rows rendered above and below the viewport to hide scroll tearing. */
const OVERSCAN = 12;

function formatTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "--:--:--" : d.toLocaleTimeString();
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
  const { logs, connected, clear, seed } = useLogStream();
  const [level, setLevel] = useState("ALL");
  const [follow, setFollow] = useState(true);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(600);
  const viewportRef = useRef<HTMLDivElement>(null);

  // Seed from the REST snapshot so the view is populated before the first
  // socket frame arrives.
  useEffect(() => {
    api
      .logs(200)
      .then(seed)
      .catch(() => {
        // The socket will fill it in; an empty seed is not an error state.
      });
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
  const first = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const last = Math.min(total, first + visibleCount);
  const window = filtered.slice(first, last);

  return (
    <div className={s.logs}>
      <div className={s.bar}>
        <div className={s.barLeft}>
          <Badge tone={connected ? "success" : "danger"} dot>
            {connected ? "Live" : "Disconnected"}
          </Badge>
          <span className={s.count}>
            {total.toLocaleString()} line{total !== 1 ? "s" : ""}
            {logs.length >= LOG_BUFFER_LIMIT && " (buffer full)"}
          </span>
        </div>

        <div className={s.barRight}>
          <Select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            aria-label="Filter by level"
          >
            {LEVELS.map((l) => (
              <option key={l} value={l}>
                {l}
              </option>
            ))}
          </Select>

          <span className={s.count}>Follow</span>
          <Toggle checked={follow} onChange={setFollow} aria-label="Follow tail" />

          <Button size="sm" variant="ghost" onClick={clear}>
            <TrashIcon size={13} />
            Clear
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
            Bottom
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
              title="No log lines"
              body={
                level === "ALL"
                  ? "Waiting for the backend to emit something."
                  : `Nothing at ${level}. Try a lower level.`
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
                  <span className={s.ts}>{formatTime(entry.ts)}</span>
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
