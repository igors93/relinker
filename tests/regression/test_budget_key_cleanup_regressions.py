"""Regression tests: RetryBudget expired-key cleanup prevents unbounded memory growth."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from relinker import RetryBudget
from relinker.budget import _CLEANUP_INTERVAL

# ---------------------------------------------------------------------------
# Amortized cleanup removes fully-expired keys
# ---------------------------------------------------------------------------


def test_expired_keys_removed_after_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keys whose reservations have all expired must not remain in _reservations."""
    budget = RetryBudget(max_retries=3, per=1.0)
    controlled_time = 0.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    n_keys = 50
    for i in range(n_keys):
        budget._reserve(f"key-{i}", current_time=0.0, not_before=0.0)

    assert len(budget._reservations) == n_keys

    # Advance time past the rolling window so all reservations expire.
    controlled_time = 10.0

    # Trigger cleanup by calling cleanup() directly.
    budget.cleanup()

    assert len(budget._reservations) == 0, (
        "All expired keys should have been removed after cleanup()"
    )


def test_active_keys_not_removed_by_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keys with at least one non-expired reservation must be kept."""
    budget = RetryBudget(max_retries=3, per=5.0)
    controlled_time = 0.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    budget._reserve("active", current_time=0.0, not_before=0.0)

    # Advance time but stay within the window.
    controlled_time = 3.0
    budget.cleanup()

    assert "active" in budget._reservations


def test_future_reservations_not_removed_by_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keys with future (queued) reservations must not be removed."""
    budget = RetryBudget(max_retries=3, per=2.0)
    controlled_time = 100.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    # Reserve a slot 5 seconds in the future from now (t=105), so it is
    # outside the expiry boundary (current - per = 100 - 2 = 98).
    budget._reserve("future", current_time=controlled_time, not_before=controlled_time + 5.0)

    # Cleanup at t=100: boundary is 98, reservation at t=105 is not expired.
    budget.cleanup()

    assert "future" in budget._reservations


def test_amortized_cleanup_fires_after_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired keys should be cleaned up automatically after _CLEANUP_INTERVAL operations."""
    budget = RetryBudget(max_retries=2, per=1.0)
    controlled_time = 0.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    # Populate N unique expired keys.
    n_keys = 30
    for i in range(n_keys):
        budget._reserve(f"old-key-{i}", current_time=0.0, not_before=0.0)

    controlled_time = 10.0  # All reservations are now expired.

    # Trigger _CLEANUP_INTERVAL operations to fire the amortized sweep.
    for _i in range(_CLEANUP_INTERVAL):
        budget._reserve("trigger", current_time=controlled_time, not_before=controlled_time)
        reservation = budget._reservations["trigger"][-1]
        budget._release(reservation)

    # All the old expired keys should have been cleaned up at some point.
    for i in range(n_keys):
        assert f"old-key-{i}" not in budget._reservations, (
            f"key old-key-{i} should have been removed by amortized cleanup"
        )


# ---------------------------------------------------------------------------
# cleanup() does not disturb valid state
# ---------------------------------------------------------------------------


def test_cleanup_preserves_capacity_and_first_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    """cleanup() must not change the observable capacity or first legal slot."""
    budget = RetryBudget(max_retries=3, per=2.0)
    controlled_time = 0.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    budget._reserve("api", current_time=0.0, not_before=0.0)
    budget._reserve("api", current_time=0.0, not_before=0.0)

    snap_before = budget.snapshot("api")
    budget.cleanup()
    snap_after = budget.snapshot("api")

    assert snap_before.active == snap_after.active
    assert snap_before.available == snap_after.available
    assert snap_before.capacity == snap_after.capacity


def test_cleanup_with_no_keys_is_safe() -> None:
    """cleanup() on an empty budget must not raise."""
    budget = RetryBudget(max_retries=5, per=1.0)
    budget.cleanup()  # must not raise


def test_release_idempotent_after_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    """_release() called repeatedly after cleanup must not raise."""
    budget = RetryBudget(max_retries=3, per=1.0)
    controlled_time = 0.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    r = budget._reserve("api", current_time=0.0, not_before=0.0)

    controlled_time = 5.0
    budget.cleanup()

    # The key was removed by cleanup; _release must still be harmless.
    budget._release(r)
    budget._release(r)


# ---------------------------------------------------------------------------
# Decimal period precision preserved after cleanup
# ---------------------------------------------------------------------------


def test_cleanup_preserves_decimal_period_invariants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cleanup must not corrupt the rolling-window arithmetic for decimal periods."""
    budget = RetryBudget(max_retries=2, per=0.1)
    controlled_time = 0.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    r1 = budget._reserve("api", current_time=0.0, not_before=0.0)
    budget._reserve("api", current_time=0.0, not_before=0.0)

    # Both slots are placed correctly (within the 0.1s window).
    snap = budget.snapshot("api")
    assert snap.capacity == 2
    assert snap.active == 2

    # Release one slot — capacity should increase.
    budget._release(r1)
    snap2 = budget.snapshot("api")
    assert snap2.available >= 1

    # Advance time to expire all reservations, run cleanup.
    controlled_time = 1.0
    budget.cleanup()

    # After cleanup the key is gone; a fresh reservation at t=1 must work fine.
    r3 = budget._reserve("api", current_time=controlled_time, not_before=controlled_time)
    assert r3.scheduled_at == controlled_time


# ---------------------------------------------------------------------------
# Concurrency safety
# ---------------------------------------------------------------------------


def test_concurrent_cleanup_and_reserve_are_safe() -> None:
    """Concurrent reserve + cleanup must not corrupt internal state."""
    budget = RetryBudget(max_retries=10, per=1.0)
    workers = 20
    barrier = Barrier(workers)

    def work(i: int) -> None:
        barrier.wait(timeout=5)
        for _ in range(5):
            r = budget._reserve(f"key-{i}", current_time=0.0, not_before=0.0)
            budget._release(r)
        budget.cleanup()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(work, i) for i in range(workers)]
        for future in futures:
            future.result()


def test_concurrent_snapshot_and_cleanup_are_safe() -> None:
    """Concurrent snapshots and cleanup must not raise or produce invalid results."""
    budget = RetryBudget(max_retries=5, per=2.0)

    for i in range(10):
        budget._reserve(f"slot-{i}", current_time=0.0, not_before=0.0)

    workers = 16
    barrier = Barrier(workers)
    results: list[int] = []

    def read(i: int) -> None:
        barrier.wait(timeout=5)
        if i % 4 == 0:
            budget.cleanup()
        else:
            snap = budget.snapshot(f"slot-{i % 10}")
            results.append(snap.capacity)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(read, i) for i in range(workers)]
        for future in futures:
            future.result()

    assert all(c == 5 for c in results)
