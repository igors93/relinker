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

import pytest

from relinker import RetryBudget


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
    assert snap.available == 5


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
    # per=1e12 ensures any reservation at scheduled_at=0 stays within the window
    budget = RetryBudget(max_retries=3, per=1e12)
    budget._reserve("api", current_time=0, not_before=0)
    budget._reserve("api", current_time=0, not_before=0)
    snap = budget.snapshot("api")
    assert snap.active + snap.available == snap.capacity


def test_snapshot_reflects_active_reservations() -> None:
    # per=1e12 keeps scheduled_at=0 reservations well within the rolling window
    budget = RetryBudget(max_retries=3, per=1e12)
    budget._reserve("api", current_time=0, not_before=0)
    budget._reserve("api", current_time=0, not_before=0)
    snap = budget.snapshot("api")
    assert snap.active == 2
    assert snap.available == 1


def test_snapshot_excludes_expired_reservations() -> None:
    # per=1e-10 is so small that scheduled_at=0 is always outside the current window
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
