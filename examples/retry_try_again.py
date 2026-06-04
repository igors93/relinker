"""
Example: Using TryAgain for explicit retry control.

TryAgain lets you request another attempt from inside a function, even when
the exception type does not match the configured retry condition.
"""

from __future__ import annotations

from retryflow import RetryPolicy, TryAgain

# --- Fake service that returns "pending" a few times ---


class FakeJobService:
    def __init__(self, pending_count: int) -> None:
        self._pending = pending_count
        self._calls = 0

    def poll_status(self) -> str:
        self._calls += 1
        if self._pending > 0:
            self._pending -= 1
            return "pending"
        return "done"


# --- Example 1: poll until ready ---


def example_poll_until_ready() -> None:
    print("=== Poll until ready ===")
    service = FakeJobService(pending_count=3)

    policy = RetryPolicy().attempts(10).fixed_delay(0)

    def check_job() -> str:
        status = service.poll_status()
        if status == "pending":
            raise TryAgain(f"job still pending (call {service._calls})")
        return status

    result = policy.run(check_job)
    print(f"Final status: {result}")  # done
    print(f"Attempts: {service._calls}")


# --- Example 2: TryAgain works even with narrowed exception filter ---


def example_try_again_bypasses_filter() -> None:
    print("\n=== TryAgain bypasses exception filter ===")
    calls = [0]

    # Only retry TimeoutError — but TryAgain always retries too
    policy = RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(0)

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise TryAgain("not ready yet")
        return "ok"

    result = policy.run(task)
    print(f"Result: {result}")
    print(f"Calls: {calls[0]}")


# --- Example 3: exhaustion with fallback ---


def example_try_again_with_fallback() -> None:
    print("\n=== TryAgain exhaustion with fallback ===")

    policy = (
        RetryPolicy()
        .attempts(3)
        .fixed_delay(0)
        .fallback(lambda r: f"fallback after {r.attempt_count} attempts")
    )

    def always_pending() -> str:
        raise TryAgain("always pending")

    result = policy.run(always_pending)
    print(f"Result: {result}")


if __name__ == "__main__":
    example_poll_until_ready()
    example_try_again_bypasses_filter()
    example_try_again_with_fallback()
