"""
Example: Database-like retry patterns.

Shows how to use RetryFlow for database operations, including transient
timeouts, fallback queries, and statistics tracking.
"""

from __future__ import annotations

from examples.fake_services import UnstableDatabase
from retryflow import RetryPolicy

# --- Example 1: basic database retry ---


def example_basic_database_retry() -> None:
    print("=== Basic database retry ===")
    db = UnstableDatabase(timeout_times=2)

    # Use fixed_delay(0) so the example runs instantly.
    policy = RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(0)

    rows = policy.run(lambda: db.query("SELECT * FROM users"))

    print(f"Rows: {rows}")
    print(f"DB calls: {db.calls}")


# --- Example 2: fallback to empty result on database failure ---


def example_fallback_on_exhaustion() -> None:
    print("\n=== Fallback on database exhaustion ===")
    db = UnstableDatabase(timeout_times=99)  # always fails

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .fixed_delay(0)
        .fallback(lambda r: [])  # return empty list as fallback
    )

    rows = policy.run(lambda: db.query("SELECT * FROM reports"))
    print(f"Rows (fallback): {rows}")  # []


# --- Example 3: tracking statistics per decorated function ---


def example_statistics_tracking() -> None:
    print("\n=== Statistics tracking ===")

    db = UnstableDatabase(timeout_times=1)
    policy = RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(0)

    @policy
    def load_users() -> list[dict[str, object]]:
        return db.query("SELECT * FROM users")

    load_users()
    load_users()
    load_users()

    snap = load_users.retry_stats.snapshot()  # type: ignore[attr-defined]
    print(f"Calls: {snap.calls}")
    print(f"Successes: {snap.successes}")
    print(f"Average attempts: {snap.average_attempts:.1f}")


if __name__ == "__main__":
    example_basic_database_retry()
    example_fallback_on_exhaustion()
    example_statistics_tracking()
