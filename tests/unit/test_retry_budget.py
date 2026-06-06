from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from relinker import InvalidRetryConfigError, RetryBudget


def test_valid_construction_and_identity_semantics() -> None:
    budget = RetryBudget(max_retries=2, per=10)
    other = RetryBudget(max_retries=2, per=10)

    assert budget.max_retries == 2
    assert budget.per == 10.0
    assert budget is not other
    assert budget != other
    assert len({budget, other}) == 2


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "2"])
def test_invalid_max_retries(value: object) -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryBudget(max_retries=value, per=10)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [0, -1, True, float("nan"), float("inf"), "10"])
def test_invalid_period(value: object) -> None:
    with pytest.raises(InvalidRetryConfigError):
        RetryBudget(max_retries=1, per=value)  # type: ignore[arg-type]


def test_reserves_up_to_capacity_then_moves_to_boundary() -> None:
    budget = RetryBudget(max_retries=2, per=10)

    first = budget._reserve("api", current_time=0, not_before=0)
    second = budget._reserve("api", current_time=0, not_before=0)
    third = budget._reserve("api", current_time=0, not_before=0)

    assert [first.scheduled_at, second.scheduled_at, third.scheduled_at] == [0, 0, 10]


def test_exact_period_boundary_expires_old_reservation() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    budget._reserve("api", current_time=0, not_before=0)

    reservation = budget._reserve("api", current_time=10, not_before=10)

    assert reservation.scheduled_at == 10


def test_future_not_before_is_respected() -> None:
    budget = RetryBudget(max_retries=2, per=10)

    reservation = budget._reserve("api", current_time=2, not_before=7)

    assert reservation.scheduled_at == 7


def test_keys_are_isolated_and_same_key_is_shared() -> None:
    budget = RetryBudget(max_retries=1, per=10)

    assert budget._reserve("a", current_time=0, not_before=0).scheduled_at == 0
    assert budget._reserve("b", current_time=0, not_before=0).scheduled_at == 0
    assert budget._reserve("a", current_time=0, not_before=0).scheduled_at == 10


def test_release_is_exact_idempotent_and_removes_empty_key() -> None:
    budget = RetryBudget(max_retries=2, per=10)
    first = budget._reserve("api", current_time=0, not_before=0)
    second = budget._reserve("api", current_time=0, not_before=0)

    budget._release(first)
    budget._release(first)
    assert [item.token for item in budget._reservations["api"]] == [second.token]

    budget._release(second)
    assert "api" not in budget._reservations


def test_different_budget_objects_do_not_share_capacity() -> None:
    first = RetryBudget(max_retries=1, per=10)
    second = RetryBudget(max_retries=1, per=10)

    assert first._reserve("api", current_time=0, not_before=0).scheduled_at == 0
    assert second._reserve("api", current_time=0, not_before=0).scheduled_at == 0


def test_releasing_expired_or_unknown_reservation_is_harmless() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    reservation = budget._reserve("api", current_time=0, not_before=0)
    budget._reserve("api", current_time=10, not_before=10)

    budget._release(reservation)
    budget._release(reservation)


def test_reservations_satisfy_capacity_and_respect_not_before() -> None:
    budget = RetryBudget(max_retries=2, per=10)
    not_befores = (3, 1, 20, 4, 21)
    reservations = [
        budget._reserve("api", current_time=0, not_before=nb) for nb in not_befores
    ]
    times = [r.scheduled_at for r in reservations]

    for r, nb in zip(reservations, not_befores, strict=True):
        assert r.scheduled_at >= nb

    for t in times:
        window_count = sum(1 for s in times if s > t - budget.per and s <= t)
        assert window_count <= budget.max_retries


def test_thread_race_does_not_oversubscribe() -> None:
    budget = RetryBudget(max_retries=3, per=10)

    def reserve(_: int) -> float:
        return budget._reserve("api", current_time=0, not_before=0).scheduled_at

    with ThreadPoolExecutor(max_workers=20) as executor:
        times = sorted(executor.map(reserve, range(30)))

    assert times == [float(period * 10) for period in range(10) for _ in range(3)]
