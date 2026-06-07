"""Regression tests for Idea 4: budget reservation uses the earliest valid slot.

The bug: `_reserve` contained `candidate = max(candidate, reservations[-1].scheduled_at)`
which forced every new reservation to be at least as late as the most recently appended
one. This prevented using an earlier valid slot when a previous reservation had a larger
not_before than the new one.

With the fix: the FIFO line is removed. The capacity while-loop checks whether adding
the candidate would keep every rolling window within capacity, including windows that
also contain future reservations. When the candidate is illegal, it moves to the next
boundary where an existing reservation leaves a window. `_prune` is updated to filter
all expired items (not just from the front).

All tests that confirm the new (correct) behavior are below. The test
`test_reservations_remain_ordered` in test_retry_budget.py has been updated to verify the
capacity invariant instead of the FIFO ordering invariant.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from relinker import RetryBudget


def _assert_capacity_windows(times: list[float], *, capacity: int, per: float) -> None:
    for end in times:
        count = sum(1 for scheduled_at in times if end - per < scheduled_at <= end)
        assert count <= capacity


def test_distant_future_reservation_does_not_block_earlier_legal_slot() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    future = budget._reserve("api", current_time=0, not_before=100)

    earlier = budget._reserve("api", current_time=0, not_before=0)

    assert future.scheduled_at == 100
    assert earlier.scheduled_at == 0


def test_near_future_reservation_blocks_earlier_slot_when_window_would_overfill() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    future = budget._reserve("api", current_time=0, not_before=5)

    earlier = budget._reserve("api", current_time=0, not_before=0)

    assert future.scheduled_at == 5
    assert earlier.scheduled_at == 15


def test_capacity_two_uses_first_legal_slot_with_mixed_existing_reservations() -> None:
    budget = RetryBudget(max_retries=2, per=10)
    first = budget._reserve("api", current_time=0, not_before=1)
    second = budget._reserve("api", current_time=0, not_before=3)
    distant = budget._reserve("api", current_time=0, not_before=20)

    mixed = budget._reserve("api", current_time=0, not_before=4)

    times = [first.scheduled_at, second.scheduled_at, distant.scheduled_at, mixed.scheduled_at]
    assert times == [1, 3, 20, 11]
    _assert_capacity_windows(times, capacity=budget.max_retries, per=budget.per)


def test_exact_boundaries_are_available_when_old_reservation_reaches_period() -> None:
    budget = RetryBudget(max_retries=1, per=10)

    reservations = [
        budget._reserve("api", current_time=0, not_before=0),
        budget._reserve("api", current_time=0, not_before=10),
        budget._reserve("api", current_time=0, not_before=20),
    ]

    times = [reservation.scheduled_at for reservation in reservations]
    assert times == [0, 10, 20]
    _assert_capacity_windows(times, capacity=budget.max_retries, per=budget.per)


def test_cancelled_reservation_stops_influencing_earliest_slot() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    cancelled = budget._reserve("api", current_time=0, not_before=0)
    blocked = budget._reserve("api", current_time=0, not_before=0)
    assert blocked.scheduled_at == 10

    budget._release(cancelled)
    replacement = budget._reserve("api", current_time=0, not_before=0)

    assert replacement.scheduled_at == 0


def test_concurrent_reservations_respect_capacity_without_oversubscription() -> None:
    budget = RetryBudget(max_retries=3, per=10)
    not_befores = [0, 3, 1, 20, 7, 4, 9, 30, 2, 6, 12, 18]

    def reserve(not_before: float) -> tuple[float, float]:
        reservation = budget._reserve("api", current_time=0, not_before=not_before)
        return not_before, reservation.scheduled_at

    with ThreadPoolExecutor(max_workers=8) as executor:
        pairs = list(executor.map(reserve, not_befores))

    times = [scheduled_at for _, scheduled_at in pairs]
    for not_before, scheduled_at in pairs:
        assert scheduled_at >= not_before
    _assert_capacity_windows(times, capacity=budget.max_retries, per=budget.per)


def test_reserve_uses_earlier_slot_when_later_reservation_exists() -> None:
    """A new request with smaller not_before can use an earlier slot than existing ones.

    With the FIFO bug: b forced to t=5 (behind a at t=5).
    With the fix: b correctly placed at t=0 (earliest valid slot).
    """
    budget = RetryBudget(max_retries=2, per=10)
    a = budget._reserve("api", current_time=0, not_before=5)
    assert a.scheduled_at == 5

    b = budget._reserve("api", current_time=0, not_before=0)
    assert b.scheduled_at == 0, (
        f"Expected t=0 (earliest valid slot). Got t={b.scheduled_at}. "
        "FIFO enforcement caused b to be pushed behind a at t=5."
    )


def test_capacity_enforced_when_earlier_slot_used() -> None:
    """Placing a reservation earlier than an existing one still respects capacity.

    After fix: a at t=5, b at t=0 (earlier), c must go to t=10 (both earlier slots taken).
    """
    budget = RetryBudget(max_retries=2, per=10)
    a = budget._reserve("api", current_time=0, not_before=5)
    b = budget._reserve("api", current_time=0, not_before=0)
    c = budget._reserve("api", current_time=0, not_before=0)

    assert a.scheduled_at == 5
    assert b.scheduled_at == 0
    # Window (-10, 0] has b(0) and (0-10, 0] does not contain a(5) → count=1 ≤ 2
    # Window (-5, 5]  has a(5) and b(0) → count=2 ≤ 2
    # Window (0, 10]  has a(5) and c → so c must be at 10 to stay ≤ 2
    assert c.scheduled_at == 10, (
        f"Expected c at t=10 (both t=0 and t=5 are taken). Got t={c.scheduled_at}."
    )


def test_out_of_order_not_before_produces_earliest_slots() -> None:
    """Multiple reservations with mixed not_before values go to earliest valid slots.

    not_before sequence: 3, 1, 20, 4, 21.
    Expected scheduled_at:  3, 1, 20, 11, 21.
    """
    budget = RetryBudget(max_retries=2, per=10)
    not_befores = (3, 1, 20, 4, 21)
    reservations = [budget._reserve("api", current_time=0, not_before=nb) for nb in not_befores]
    times = [r.scheduled_at for r in reservations]

    # Each reservation is no earlier than its not_before.
    for r, nb in zip(reservations, not_befores, strict=True):
        assert r.scheduled_at >= nb, f"scheduled_at={r.scheduled_at} < not_before={nb}"

    # Capacity constraint holds for every reservation's window.
    per = budget.per
    for t in times:
        window_count = sum(1 for s in times if s > t - per and s <= t)
        assert window_count <= budget.max_retries, (
            f"Capacity violated at t={t}: {window_count} reservations in ({t - per}, {t}]"
        )

    # Exact values after earliest-slot scheduling.
    assert times == [3, 1, 20, 11, 21], (
        f"Expected earliest-slot times [3, 1, 20, 11, 21], got {times}."
    )


def test_expired_out_of_order_items_are_pruned() -> None:
    """_prune correctly removes all expired items even when deque is not sorted.

    After fix: deque may contain [a at 5, b at 0] (non-sorted).
    Pruning at current=6 with per=5: boundary=1. Items with scheduled_at ≤ 1 are expired.
    b at 0 should be pruned even though it is not at the front of the deque.
    """
    budget = RetryBudget(max_retries=2, per=5)
    a = budget._reserve("api", current_time=0, not_before=4)  # a at t=4
    b = budget._reserve("api", current_time=0, not_before=0)  # b at t=0 (earliest slot)

    assert a.scheduled_at == 4
    assert b.scheduled_at == 0

    # Now prune at current=6; boundary=6-5=1. b(0) and a(4) both ≤ 1? a(4)>1 stays, b(0)≤1 prunes.
    # After pruning, only a remains; new reserve should find 1 item, not 2.
    c = budget._reserve("api", current_time=6, not_before=6)
    # At candidate=6: after prune(current=6), b(0) is expired, a(4) stays (4>1).
    # active for boundary=6-5=1: a(4>1) → count=1 < 2 → break. c at t=6.
    assert c.scheduled_at == 6, (
        f"Expected c at t=6 (b expired, only a remains). Got t={c.scheduled_at}. "
        "b may not have been pruned because _prune only removed from the front."
    )
