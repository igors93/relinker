"""Clock helpers."""

from __future__ import annotations

from time import monotonic


def now() -> float:
    """Return a monotonic timestamp suitable for durations."""
    return monotonic()
