"""Stop strategies."""

from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.base import StopMixin, StopStrategy
from relinker.stop.composite import AllStopStrategy, AnyStopStrategy
from relinker.stop.forever import StopForever
from relinker.stop.max_time import StopAfterDelay

__all__ = [
    "AllStopStrategy",
    "AnyStopStrategy",
    "StopAfterAttempt",
    "StopAfterDelay",
    "StopForever",
    "StopMixin",
    "StopStrategy",
]
