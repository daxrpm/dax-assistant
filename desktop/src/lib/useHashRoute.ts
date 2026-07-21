import { useEffect, useState } from "react";

/**
 * Minimal hash router.
 *
 * PLAN.md 6.3 flags history-mode routing from Tauri's custom protocol as
 * UNCERTAIN and names hash routing the safe fallback. We take the fallback: it
 * is guaranteed to work from any origin, needs no dependency, and nothing in
 * the app requires real URLs.
 */
export function useHashRoute(fallback: string): [string, (next: string) => void] {
  const [route, setRoute] = useState(() => window.location.hash.slice(1) || fallback);

  useEffect(() => {
    const onChange = () => setRoute(window.location.hash.slice(1) || fallback);
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, [fallback]);

  const navigate = (next: string) => {
    window.location.hash = next;
  };

  return [route, navigate];
}
