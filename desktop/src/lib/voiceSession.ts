/**
 * The voice session countdown.
 *
 * PLAN.md 5.0 calls this out as the number that was previously invisible: the
 * session id is what the agent uses as its conversation key, so whether it is
 * still alive is exactly what determines whether Dax remembers the last thing
 * you said.
 *
 * `VoicePipeline._resume_or_start_session` expires a session after
 * `voice.session_ttl_minutes` of real inactivity. Two things about that are
 * not on the wire, and the UI must be honest about both:
 *
 *   1. **The remaining time is never sent.** `/ws/voice` emits state,
 *      transcript, speaker, level and error frames only (PLAN 4.6). The deck
 *      therefore measures inactivity itself, from the last non-level frame it
 *      observed. That is a real measurement, but it starts when the client
 *      connects — attaching mid-session under-reports elapsed idle time.
 *   2. **The TTL is not exposed.** `GET /api/config` returns ~40 voice fields
 *      and `session_ttl_minutes` is not among them
 *      (`src/dax/web/routes/config.py`). The countdown is therefore computed
 *      against the backend default below and is rendered with a `≈` marker so
 *      it never reads as authoritative.
 *
 * When the backend starts reporting either value, replace this module's use
 * with the real one — the deck already renders an unknown TTL as "—".
 */

/** `VoiceConfig.session_ttl_minutes` default, `src/dax/core/config.py:100`. */
export const SESSION_TTL_MINUTES_DEFAULT = 10;

export interface SessionCountdown {
  /** Seconds left before the session is assumed expired, or null if unknown. */
  remainingSeconds: number | null;
  /** True when the TTL is the assumed default rather than a reported value. */
  approximate: boolean;
}

export function sessionCountdown(
  lastEventAt: number | null,
  now: number,
  ttlMinutes: number | null = SESSION_TTL_MINUTES_DEFAULT,
): SessionCountdown {
  if (lastEventAt === null || ttlMinutes === null || ttlMinutes <= 0) {
    return { remainingSeconds: null, approximate: true };
  }
  const elapsed = (now - lastEventAt) / 1000;
  return {
    remainingSeconds: Math.max(0, ttlMinutes * 60 - elapsed),
    approximate: true,
  };
}

/** `m:ss`, tabular so the column does not jitter as digits change. */
export function formatCountdown(seconds: number | null): string {
  if (seconds === null) return "—";
  const total = Math.floor(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}
