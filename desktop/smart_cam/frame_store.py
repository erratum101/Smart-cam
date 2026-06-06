"""Latest-frame buffer: consumers always read the freshest frame, no backlog."""

from __future__ import annotations

import threading


class FrameStore:
    """Thread-safe single-slot frame holder (replaces Queue for video)."""

    __slots__ = ("_lock", "_frame", "_generation")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frame: object | None = None
        self._generation = 0

    def publish(self, frame: object) -> None:
        with self._lock:
            self._frame = frame
            self._generation += 1

    def take_latest(self) -> tuple[object | None, int]:
        with self._lock:
            return self._frame, self._generation

    def clear(self) -> None:
        with self._lock:
            self._frame = None
            self._generation += 1
