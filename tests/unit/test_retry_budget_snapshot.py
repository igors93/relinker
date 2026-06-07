"""Tests for RetryBudget.snapshot() → RetryBudgetSnapshot (Idea 3).

Contract:
- RetryBudgetSnapshot is a frozen dataclass importable from relinker
- snapshot(key) returns a RetryBudgetSnapshot with fields:
    key, capacity, per, active, available
- active reflects reservations within the current rolling window
- available == capacity - active (always)
- expired reservations do not count as active
- keys are isolated: reservations under one key don't affect another key's snapshot
"""

from __future__ import annotations

import dataclasses
from concurrent.futures import ThreadPoolExecutor

import pytest

from relinker import InvalidRetryConfigError, RetryBudget


def _set_budget_clock(monkeypatch: pytest.MonkeyPatch, value: float) -> None:
    monkeypatch.setattr("relinker.budget._monotonic", lambda: value)


def test_snapshot_importable_from_public_api() -> None:
    from relinker import RetryBudgetSnapshot  # noqa: F401  # must not raise

    assert RetryBudgetSnapshot is not None


def test_snapshot_returns_correct_type() -> None:
    from relinker import RetryBudgetSnapshot

    budget = RetryBudget(max_retries=3, per=60.0)
    snap = budget.snapshot("my-key")
    assert isinstance(snap, RetryBudgetSnapshot)


def test_snapshot_unused_key_shows_zero_active() -> None:
    budget = RetryBudget(max_retries=5, per=60.0)
    snap = budget.snapshot("unused-key")
    assert snap.key == "unused-key"
    assert snap.active == 0
    assert snap.queued == 0
    assert snap.available == 5
    assert snap.available_now == 5
    assert snap.next_available_in == 0


def test_snapshot_reports_correct_capacity_and_per() -> None:
    budget = RetryBudget(max_retries=7, per=30.0)
    snap = budget.snapshot("some-key")
    assert snap.capacity == 7
    assert snap.per == 30.0


def test_snapshot_is_read_only() -> None:
    budget = RetryBudget(max_retries=3, per=60.0)
    snap = budget.snapshot("k")
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        snap.active = 99  # type: ignore[misc]


def test_snapshot_active_plus_available_equals_capacity() -> None:
    budget = RetryBudget(max_retries=3, per=1e12)
    budget._reserve("api", current_time=0, not_before=0)
    budget._reserve("api", current_time=0, not_before=0)
    snap = budget.snapshot("api")
    assert snap.active + snap.available == snap.capacity


def test_snapshot_reflects_active_reservations() -> None:
    budget = RetryBudget(max_retries=3, per=1e12)
    budget._reserve("api", current_time=0, not_before=0)
    budget._reserve("api", current_time=0, not_before=0)
    snap = budget.snapshot("api")
    assert snap.active == 2
    assert snap.available == 1


def test_snapshot_excludes_expired_reservations() -> None:
    budget = RetryBudget(max_retries=3, per=1e-10)
    budget._reserve("api", current_time=0, not_before=0)
    snap = budget.snapshot("api")
    assert snap.active == 0
    assert snap.available == 3


def test_snapshot_key_isolation() -> None:
    budget = RetryBudget(max_retries=3, per=1e12)
    budget._reserve("api", current_time=0, not_before=0)
    snap = budget.snapshot("other-key")
    assert snap.active == 0
    assert snap.available == 3


@pytest.mark.parametrize("key", ["", "   ", 123])
def test_snapshot_rejects_invalid_key(key: object) -> None:
    budget = RetryBudget(max_retries=1, per=10)

    with pytest.raises(InvalidRetryConfigError):
        budget.snapshot(key)  # type: ignore[arg-type]


def test_snapshot_distinguishes_active_and_future_reservations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_budget_clock(monkeypatch, 10)
    budget = RetryBudget(max_retries=2, per=10)
    budget._reserve("api", current_time=10, not_before=10)
    budget._reserve("api", current_time=10, not_before=15)

    snap = budget.snapshot("api")

    assert snap.active == 1
    assert snap.queued == 1
    assert snap.available == 0
    assert snap.available_now == 0
    assert snap.next_available_in == 10


def test_snapshot_future_distant_does_not_reduce_available_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_budget_clock(monkeypatch, 0)
    budget = RetryBudget(max_retries=1, per=10)
    budget._reserve("api", current_time=0, not_before=100)

    snap = budget.snapshot("api")

    assert snap.active == 0
    assert snap.queued == 1
    assert snap.available == 1
    assert snap.available_now == 1
    assert snap.next_available_in == 0


def test_snapshot_reports_next_available_when_capacity_is_full_now(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_budget_clock(monkeypatch, 5)
    budget = RetryBudget(max_retries=1, per=10)
    budget._reserve("api", current_time=0, not_before=0)

    snap = budget.snapshot("api")

    assert snap.active == 1
    assert snap.queued == 0
    assert snap.available == 0
    assert snap.next_available_in == 5


def test_snapshot_ignores_expired_reservations_with_controlled_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_budget_clock(monkeypatch, 10)
    budget = RetryBudget(max_retries=1, per=10)
    budget._reserve("api", current_time=0, not_before=0)

    snap = budget.snapshot("api")

    assert snap.active == 0
    assert snap.queued == 0
    assert snap.available == 1
    assert snap.next_available_in == 0


def test_snapshot_remains_coherent_with_more_future_reservations_than_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_budget_clock(monkeypatch, 0)
    budget = RetryBudget(max_retries=1, per=10)
    budget._reserve("api", current_time=0, not_before=20)
    budget._reserve("api", current_time=0, not_before=30)
    budget._reserve("api", current_time=0, not_before=40)

    snap = budget.snapshot("api")

    assert snap.active == 0
    assert snap.queued == 3
    assert snap.available >= 0
    assert snap.active <= snap.capacity


def test_snapshot_concurrent_reads_are_coherent(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_budget_clock(monkeypatch, 5)
    budget = RetryBudget(max_retries=2, per=10)
    budget._reserve("api", current_time=0, not_before=0)
    budget._reserve("api", current_time=0, not_before=15)

    def read_snapshot(_: int) -> tuple[int, int, int, float]:
        snap = budget.snapshot("api")
        return snap.active, snap.queued, snap.available, snap.next_available_in

    with ThreadPoolExecutor(max_workers=8) as executor:
        snapshots = list(executor.map(read_snapshot, range(40)))

    assert set(snapshots) == {(1, 1, 1, 0)}
