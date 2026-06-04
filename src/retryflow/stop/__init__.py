"""Stop strategies."""

from retryflow.stop.attempts import StopAfterAttempt
from retryflow.stop.base import StopMixin, StopStrategy
from retryflow.stop.composite import AllStopStrategy, AnyStopStrategy
from retryflow.stop.forever import StopForever
from retryflow.stop.max_time import StopAfterDelay

__all__ = [
    "AllStopStrategy",
    "AnyStopStrategy",
    "StopAfterAttempt",
    "StopAfterDelay",
    "StopForever",
    "StopMixin",
    "StopStrategy",
]
