"""Stop strategy that never stops by itself."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.stop.base import StopMixin


@dataclass(frozen=True, slots=True)
class StopForever(StopMixin):
    """
    Never stops based on attempts or elapsed time.

    Relinker allows this because some applications need it. The library should
    give control to the user and only reject impossible configurations.
    """

    def should_stop(self, attempt_number: int, elapsed: float) -> bool:
        """Return False forever."""
        return False
