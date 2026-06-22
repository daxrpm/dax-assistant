import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@heroui/react";
import { Trash2, ArrowDownToLine } from "lucide-react";
import { useLogStream } from "../hooks/useLogStream";
import { Select, Badge } from "../components/ui";
import { cn } from "../lib/cn";

const LEVELS = ["ALL", "DEBUG", "INFO", "WARNING", "ERROR"] as const;

const LEVEL_COLOR: Record<string, string> = {
  DEBUG: "text-muted",
  INFO: "text-accent",
  WARNING: "text-warning",
  ERROR: "text-danger",
  CRITICAL: "text-danger",
};

export function LogsPage() {
  const { logs, connected, clear } = useLogStream();
  const [level, setLevel] = useState<string>("ALL");
  const [follow, setFollow] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(
    () => (level === "ALL" ? logs : logs.filter((l) => l.level === level)),
    [logs, level],
  );

  useEffect(() => {
    if (follow) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
    }
  }, [filtered, follow]);

  return (
    <div className="flex h-full flex-col p-6">
      <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col overflow-hidden">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Badge color={connected ? "success" : "danger"}>
              {connected ? "live" : "disconnected"}
            </Badge>
            <span className="text-sm text-muted">{filtered.length} lines</span>
          </div>
          <div className="flex items-center gap-2">
            <Select
              value={level}
              onChange={(e) => setLevel(e.target.value)}
              className="w-36"
            >
              {LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l}
                </option>
              ))}
            </Select>
            <Button
              variant={follow ? "primary" : "tertiary"}
              size="sm"
              onPress={() => setFollow((f) => !f)}
            >
              <ArrowDownToLine size={15} />
              Follow
            </Button>
            <Button variant="tertiary" size="sm" onPress={clear}>
              <Trash2 size={15} />
              Clear
            </Button>
          </div>
        </div>

        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            const atBottom =
              el.scrollHeight - el.scrollTop - el.clientHeight < 40;
            if (!atBottom && follow) setFollow(false);
          }}
          className="min-h-0 flex-1 overflow-y-auto rounded-2xl border border-separator bg-surface p-3 font-mono text-xs scroll-slim"
        >
          {filtered.length === 0 ? (
            <p className="p-4 text-center text-muted">No log entries.</p>
          ) : (
            filtered.map((l, i) => (
              <div
                key={i}
                className="flex gap-3 whitespace-pre-wrap break-words border-b border-separator/40 py-1 last:border-0"
              >
                <span className="shrink-0 text-muted">
                  {new Date(l.ts).toLocaleTimeString()}
                </span>
                <span className={cn("w-16 shrink-0 font-semibold", LEVEL_COLOR[l.level])}>
                  {l.level}
                </span>
                <span className="shrink-0 text-muted">{l.logger}</span>
                <span className="flex-1">{l.message}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
