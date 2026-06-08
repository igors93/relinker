"""Property tests for RetryBudget rolling-window invariants."""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from relinker import RetryBudget

DECIMAL_PERIODS = (0.1, 0.2, 0.3, 0.4, 1.0 / 3.0, 1.0, 2.0, 5.0)


def _window_is_legal(times: list[float], *, capacity: int, per: float) -> bool:
    for window_end in times:
        count = sum(1 for scheduled_at in times if window_end - per < scheduled_at <= window_end)
        if count > capacity:
            return False
    return True


def _assert_window_capacity(times: list[float], *, capacity: int, per: float) -> None:
    assert _window_is_legal(times, capacity=capacity, per=per), (
        f"rolling-window capacity exceeded: capacity={capacity}, per={per}, times={times}"
    )


def _candidate_boundaries(existing: list[float], *, not_before: float, per: float) -> list[float]:
    candidates = {not_before}
    for scheduled_at in existing:
        boundary = scheduled_at + per
        candidates.add(boundary)
        candidates.add(math.nextafter(boundary, -math.inf))
        candidates.add(math.nextafter(boundary, math.inf))
    return sorted(candidate for candidate in candidates if candidate >= not_before)


def _reference_first_legal_slot(
    existing: list[float],
    *,
    not_before: float,
    capacity: int,
    per: float,
) -> float:
    for candidate in _candidate_boundaries(existing, not_before=not_before, per=per):
        if _window_is_legal([*existing, candidate], capacity=capacity, per=per):
            return candidate
    raise AssertionError(
        f"reference model found no legal candidate: existing={existing}, "
        f"not_before={not_before}, capacity={capacity}, per={per}"
    )


@settings(max_examples=250, deadline=None)
@given(
    capacity=st.integers(min_value=1, max_value=8),
    per=st.sampled_from(DECIMAL_PERIODS),
    not_befores=st.lists(
        st.sampled_from(
            (
                0.0,
                math.nextafter(0.1, -math.inf),
                0.1,
                math.nextafter(0.1, math.inf),
                0.2,
                0.3,
                math.nextafter(1.0 / 3.0, -math.inf),
                1.0 / 3.0,
                math.nextafter(1.0 / 3.0, math.inf),
                0.4,
                0.5,
                1.0,
                2.0,
            )
        ),
        min_size=1,
        max_size=10,
    ),
)
def test_retry_budget_matches_reference_model_for_small_float_schedules(
    capacity: int,
    per: float,
    not_befores: list[float],
) -> None:
    budget = RetryBudget(max_retries=capacity, per=per)
    scheduled: list[float] = []

    for not_before in not_befores:
        expected = _reference_first_legal_slot(
            scheduled,
            not_before=not_before,
            capacity=capacity,
            per=per,
        )
        reservation = budget._reserve("api", current_time=0.0, not_before=not_before)
        scheduled.append(reservation.scheduled_at)

        assert reservation.scheduled_at == expected
        assert reservation.scheduled_at >= not_before
        _assert_window_capacity(scheduled, capacity=capacity, per=per)


@settings(max_examples=120, deadline=None)
@given(
    per=st.sampled_from((0.1, 0.2, 0.3, 0.4, 1.0 / 3.0)),
    not_before=st.sampled_from((0.0, 0.1, 0.2, 0.3, 0.4, 1.0 / 3.0)),
)
def test_retry_budget_keys_are_independent_under_identical_schedules(
    per: float,
    not_before: float,
) -> None:
    budget = RetryBudget(max_retries=1, per=per)

    first = budget._reserve("api-a", current_time=0.0, not_before=not_before)
    second = budget._reserve("api-b", current_time=0.0, not_before=not_before)

    assert first.scheduled_at == not_before
    assert second.scheduled_at == not_before
