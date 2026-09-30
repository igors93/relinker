"""Clock helpers.

Runtime modules read the clock through ``clock.now()`` (module attribute
lookup) instead of importing ``now`` by name, so this module is the single
place where tests substitute a fake clock.
"""

from __future__ import annotations

from time import monotonic


def now() -> float:
    """Return a monotonic timestamp suitable for durations."""
    return monotonic()
