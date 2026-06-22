"""In-memory log buffer + live fan-out for the web Logs viewer.

A single :class:`LogBuffer` is installed as a stdlib ``logging`` handler on the
root logger. It keeps the most recent records in a ring buffer (served over
``GET /api/logs``) and pushes new records to any subscribed asyncio queues
(streamed over ``WS /ws/logs``).

Records can be emitted from any thread (e.g. the voice pipeline), so live
dispatch is marshalled onto the main event loop with ``call_soon_threadsafe``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any


class LogBuffer(logging.Handler):
    """Stdlib log handler that retains recent records and fans them out live."""

    def __init__(self, capacity: int = 1000) -> None:
        super().__init__()
        self._records: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register the event loop used to deliver live records to subscribers."""
        self._loop = loop

    # -- logging.Handler --

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": datetime.fromtimestamp(
                    record.created, tz=UTC
                ).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        except Exception:
            return

        self._records.append(entry)

        if self._loop is None or not self._subscribers:
            return
        # Hop onto the event loop so queue access is single-threaded.
        with contextlib.suppress(RuntimeError):  # loop closed during shutdown
            self._loop.call_soon_threadsafe(self._dispatch, entry)

    def _dispatch(self, entry: dict[str, Any]) -> None:
        for queue in self._subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(entry)

    # -- API surface --

    def recent(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return the most recent records (oldest first), capped at ``limit``."""
        if limit <= 0:
            return []
        items = list(self._records)
        return items[-limit:]

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        """Register a queue that receives every new record until unsubscribed."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)
