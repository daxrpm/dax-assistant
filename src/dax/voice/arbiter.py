"""Decide which microphone answers when several hear the same wake word.

Dax listens in more than one place: the backend host samples its own
microphone, and every capability node that is allowed to listen runs the same
detector next to its own. Standing in one room with a laptop and a server both
in earshot, a single "hey jarvis" fires both detectors within a few tens of
milliseconds of each other. Without a referee both would answer, the user would
hear two earcons, and two sessions would race for the same sentence.

The referee lives here, on the backend, because the backend is the only party
every detector is already connected to. A detector does not act on its own
detection; it *claims* the wake and waits. Claims that land inside one short
window are judged together and the loudest — the highest detector confidence,
which is the best cheap proxy for "closest to the user" — wins. Everyone else
stands down and suppresses its own detector long enough that the tail of the
same utterance cannot re-trigger it.

The window is the whole design tension. Too short and a slightly slower node
arrives after the decision and answers as a second voice; too long and every
activation pays that latency before the earcon. A few hundred milliseconds
covers realistic LAN jitter while staying under what a user reads as lag.

Nothing here is a security control. A node cannot be trusted to report an
honest score, so a node that lies simply wins its own room — which is the
capability it already has by virtue of holding a microphone. The arbiter exists
to stop duplicate answers, not to police nodes.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

# The backend's own microphone always claims under this id. Node claims use
# their device id, which can never collide with it.
HOST_SOURCE_ID = "__host__"


@dataclass
class WakeClaim:
    """One detector's bid to answer a wake word, and the verdict on it."""

    source_id: str
    score: float
    _decided: threading.Event = field(default_factory=threading.Event, repr=False)
    _won: bool = field(default=False, repr=False)

    @property
    def won(self) -> bool:
        """The verdict. Meaningless until :meth:`wait` has returned."""
        return self._won

    def wait(self, timeout: float) -> bool:
        """Block until the window closes; True when this claim may proceed.

        Returning False on timeout is deliberate. A claim whose verdict never
        arrives must not answer: a duplicate reply is worse than a missed one,
        and the user can always say the wake word again.
        """
        if not self._decided.wait(timeout):
            return False
        return self._won


class WakeArbiter:
    """Serialise concurrent wake-word detections down to a single winner.

    Thread-safety is a requirement rather than a nicety: the backend pipeline
    claims from its own capture thread while the capability hub claims from the
    event loop, so every transition below is taken under one lock.
    """

    def __init__(
        self,
        *,
        window_s: float = 0.35,
        suppress_s: float = 2.0,
        hold_timeout_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window_s = max(0.0, window_s)
        self._suppress_s = max(0.0, suppress_s)
        self._hold_timeout_s = max(1.0, hold_timeout_s)
        self._clock = clock
        self._lock = threading.Lock()
        # Claims in the window currently being judged.
        self._pending: list[WakeClaim] = []
        self._window_ends_at: float | None = None
        # Set from the moment a winner is chosen until the turn it started is
        # over. A held arbiter rejects new claims outright, which is what stops
        # the second half of "hey jarvis, pon música" from opening a new turn.
        self._held_by: str | None = None
        self._held_at: float = 0.0

    @property
    def suppress_s(self) -> float:
        """How long a losing detector should ignore its own microphone."""
        return self._suppress_s

    @property
    def held_by(self) -> str | None:
        with self._lock:
            return self._held_by if not self._hold_expired() else None

    def claim(self, source_id: str, score: float) -> WakeClaim:
        """Register a detection and return the claim to wait on.

        The claim is already decided — and lost — when another turn is in
        flight, so a caller that ignores :meth:`WakeClaim.wait` still cannot
        barge in.
        """
        claim = WakeClaim(source_id=source_id, score=float(score))
        with self._lock:
            if self._held_by is not None and not self._hold_expired():
                logger.debug(
                    "Wake claim from %s dropped — %s is mid-turn",
                    source_id,
                    self._held_by,
                )
                claim._decided.set()
                return claim
            self._held_by = None
            if self._window_ends_at is None:
                self._window_ends_at = self._clock() + self._window_s
            self._pending.append(claim)
        return claim

    def resolve_due(self) -> bool:
        """Judge the open window if it has closed. True when a verdict landed.

        Called by whoever is waiting, so the arbiter needs no timer thread of
        its own — every claimant is already blocked on the outcome.
        """
        with self._lock:
            if self._window_ends_at is None or self._clock() < self._window_ends_at:
                return False
            self._decide_locked()
            return True

    def wait_for(self, claim: WakeClaim) -> bool:
        """Block until *claim* is judged, driving the window to its close.

        This is the call every detector makes. It resolves the window itself
        rather than waiting for someone else to, so a lone claimant — the
        common case, one room with one microphone in it — still gets a verdict.
        """
        deadline = self._deadline_for(claim)
        while not claim._decided.is_set():
            remaining = deadline - self._clock()
            if remaining <= 0:
                self.resolve_due()
                break
            claim._decided.wait(min(remaining, 0.05))
        # A slow scheduler can leave the window closed but unjudged.
        if not claim._decided.is_set():
            self.resolve_due()
        return claim.wait(0.0) if claim._decided.is_set() else False

    def release(self, source_id: str) -> None:
        """Give the wake path back after *source_id* finished its turn."""
        with self._lock:
            if self._held_by == source_id:
                self._held_by = None
                logger.debug("Wake arbiter released by %s", source_id)

    def reset(self) -> None:
        """Drop all state — used when the pipeline restarts or errors out."""
        with self._lock:
            for claim in self._pending:
                claim._won = False
                claim._decided.set()
            self._pending.clear()
            self._window_ends_at = None
            self._held_by = None

    # -- internals --

    def _deadline_for(self, claim: WakeClaim) -> float:
        with self._lock:
            # An already-decided claim (rejected at claim time) has no window.
            return self._window_ends_at or self._clock()

    def _hold_expired(self) -> bool:
        """Whether a hold outlived its turn — a crashed node must not wedge us.

        Caller holds the lock.
        """
        if self._held_by is None:
            return True
        if self._clock() - self._held_at < self._hold_timeout_s:
            return False
        logger.warning(
            "Wake hold by %s expired after %.0fs — releasing",
            self._held_by,
            self._hold_timeout_s,
        )
        self._held_by = None
        return True

    def _decide_locked(self) -> None:
        pending = self._pending
        self._pending = []
        self._window_ends_at = None
        if not pending:
            return
        # Highest confidence wins; the source id breaks ties so two detectors
        # reporting an identical score still produce one deterministic winner
        # instead of depending on arrival order.
        winner = min(pending, key=lambda c: (-c.score, c.source_id))
        for claim in pending:
            claim._won = claim is winner
            claim._decided.set()
        self._held_by = winner.source_id
        self._held_at = self._clock()
        if len(pending) > 1:
            logger.info(
                "Wake word heard by %d microphones — %s answers (score=%.3f)",
                len(pending),
                winner.source_id,
                winner.score,
            )
