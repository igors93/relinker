"""Regression test: rolling-window capacity invariant with decimal period values.

The invariant: for any set of scheduled_at times produced by _reserve, no
rolling window of length `per` contains more than `max_retries` reservations.

Window definition (open left, closed right):
    window_end - per < scheduled_at <= window_end

Float arithmetic can produce rounding errors when `first + per` is computed and
then compared against existing reservations via `candidate - per < scheduled_at`,
causing a slot that should be outside the window to appear inside it.
"""

from __future__ import annotations

import pytest

from relinker import RetryBudget


def _assert_rolling_window_capacity(times: list[float], *, capacity: int, per: float) -> None:
    for window_end in times:
        count = sum(1 for scheduled_at in times if window_end - per < scheduled_at <= window_end)
        assert count <= capacity, (
            f"Capacity {capacity} exceeded at window_end={window_end}: "
            f"count={count}, per={per}, times={times}"
        )


def test_decimal_period_boundary_preserves_rolling_window_capacity() -> None:
    """_reserve with per=0.4 must not place two reservations in the same window."""
    budget = RetryBudget(max_retries=1, per=0.4)

    reservations = [
        budget._reserve("api", current_time=0.0, not_before=0.1),
        budget._reserve("api", current_time=0.0, not_before=0.0),
    ]
    times = [r.scheduled_at for r in reservations]

    _assert_rolling_window_capacity(times, capacity=budget.max_retries, per=budget.per)


@pytest.mark.parametrize(
    ("max_retries", "per", "not_befores"),
    [
        (1, 0.4, [0.1, 0.0]),
        (1, 0.1, [0.05, 0.0]),
        (1, 0.3, [0.1, 0.0]),
        (2, 0.4, [0.1, 0.2, 0.0]),
    ],
)
def test_decimal_period_capacity_invariant_parametrized(
    max_retries: int,
    per: float,
    not_befores: list[float],
) -> None:
    """Capacity invariant holds for several decimal period / not_before combinations."""
    budget = RetryBudget(max_retries=max_retries, per=per)
    reservations = [budget._reserve("api", current_time=0.0, not_before=nb) for nb in not_befores]
    times = [r.scheduled_at for r in reservations]

    for r, nb in zip(reservations, not_befores, strict=True):
        assert r.scheduled_at >= nb, f"scheduled_at={r.scheduled_at} < not_before={nb}"

    _assert_rolling_window_capacity(times, capacity=budget.max_retries, per=budget.per)
