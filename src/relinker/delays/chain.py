"""Chain delay strategy."""

from __future__ import annotations

from dataclasses import dataclass

from relinker.delays.base import DelayMixin
from relinker.exceptions import InvalidRetryConfigError
from relinker.internal.validation import ensure_safe_delay


@dataclass(frozen=True, slots=True)
class ChainDelay(DelayMixin):
    """
    Delay that follows a predefined sequence.

    When attempts exceed the sequence length, the last delay is reused. This is
    practical and predictable for production systems.
    """

    delays: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.delays:
            raise InvalidRetryConfigError("delays must contain at least one value")

        for index, delay in enumerate(self.delays):
            ensure_safe_delay(f"delays[{index}]", delay)

    def next_delay(self, attempt_number: int) -> float:
        """Return the delay for the given attempt."""
        index = max(0, attempt_number - 1)
        if index >= len(self.delays):
            return self.delays[-1]
        return self.delays[index]
