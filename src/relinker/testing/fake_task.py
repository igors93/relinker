"""Fake task helpers for tests and examples."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic

from relinker.typing import T


@dataclass
class FailingTask(Generic[T]):
    """Callable object that fails a fixed number of times and then returns a value."""

    failures_left: int
    final_value: T
    error: BaseException

    def __call__(self) -> T:
        """Run the fake task."""
        if self.failures_left > 0:
            self.failures_left -= 1
            raise self.error
        return self.final_value


@dataclass(frozen=True, slots=True)
class FailTimesBuilder:
    """Builder returned by fail_times."""

    times: int
    error: BaseException

    def then_return(self, value: T) -> FailingTask[T]:
        """Return a task that eventually returns the given value."""
        return FailingTask(self.times, value, self.error)


def fail_times(times: int, error: BaseException | None = None) -> FailTimesBuilder:
    """Create a fake task builder."""
    if times < 0:
        msg = "times must be greater than or equal to 0"
        raise ValueError(msg)
    return FailTimesBuilder(times=times, error=error or RuntimeError("planned failure"))
