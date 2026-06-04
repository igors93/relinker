"""Stop strategies."""

from retryflow.stop.attempts import StopAfterAttempt
from retryflow.stop.base import StopStrategy
from retryflow.stop.forever import StopForever
from retryflow.stop.max_time import StopAfterDelay

__all__ = [
    "StopAfterAttempt",
    "StopAfterDelay",
    "StopForever",
    "StopStrategy",
]
