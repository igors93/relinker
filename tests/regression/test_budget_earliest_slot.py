"""Regression tests for Idea 4: budget reservation uses the earliest valid slot.

The bug: `_reserve` contained `candidate = max(candidate, reservations[-1].scheduled_at)`
which forced every new reservation to be at least as late as the most recently appended
one. This prevented using an earlier valid slot when a previous reservation had a larger
not_before than the new one.

With the fix: the FIFO line is removed. The capacity while-loop finds the earliest valid
slot by using min(active) instead of active[0] (since the deque is no longer sorted).
`_prune` is updated to filter all expired items (not just from the front).

All tests that confirm the new (correct) behavior are below. The test
`test_reservations_remain_ordered` in test_retry_budget.py has been updated to verify the
capacity invariant instead of the FIFO ordering invariant.
"""

from __future__ import annotations

from relinker import RetryBudget


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
    Expected scheduled_at:  3, 1, 20, 13, 23.
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
    assert times == [3, 1, 20, 13, 23], (
        f"Expected earliest-slot times [3, 1, 20, 13, 23], got {times}."
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
