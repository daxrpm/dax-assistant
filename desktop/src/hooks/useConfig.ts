import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { FullConfig, StatusResponse } from "../api/types";

/**
 * `GET /api/config` with a manual refresh.
 *
 * Every settings tab mutates one section and then calls `refresh()` so the
 * masked-secret booleans (`*_configured`, `has_token`, …) come back from the
 * server rather than being guessed client side.
 */
export function useConfig() {
  const [config, setConfig] = useState<FullConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setConfig(await api.config());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { config, loading, error, refresh };
}

/** `GET /api/status`, optionally polled. */
export function useStatus(pollMs?: number) {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.status());
    } catch {
      // Dashboard renders a degraded state; a failed poll is not fatal.
    }
  }, []);

  useEffect(() => {
    void refresh();
    if (!pollMs) return;
    const timer = setInterval(() => void refresh(), pollMs);
    return () => clearInterval(timer);
  }, [refresh, pollMs]);

  return { status, refresh };
}
