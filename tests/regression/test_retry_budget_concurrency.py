"""Concurrent RetryBudget invariants."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from relinker import RetryBudget


def _assert_rolling_window_capacity(times: list[float], *, capacity: int, per: float) -> None:
    for window_end in times:
        count = sum(1 for scheduled_at in times if window_end - per < scheduled_at <= window_end)
        assert count <= capacity


def test_concurrent_same_key_reservations_have_unique_tokens_and_respect_capacity() -> None:
    budget = RetryBudget(max_retries=5, per=1.0)
    workers = 32
    barrier = Barrier(workers)

    def reserve(index: int) -> tuple[int, float]:
        barrier.wait(timeout=5)
        reservation = budget._reserve("api", current_time=0.0, not_before=(index % 4) * 0.1)
        return reservation.token, reservation.scheduled_at

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(reserve, range(workers)))

    tokens = [token for token, _scheduled_at in results]
    times = [scheduled_at for _token, scheduled_at in results]

    assert len(tokens) == len(set(tokens))
    _assert_rolling_window_capacity(times, capacity=budget.max_retries, per=budget.per)


def test_concurrent_different_keys_do_not_share_capacity() -> None:
    budget = RetryBudget(max_retries=1, per=10.0)
    workers = 12
    barrier = Barrier(workers)

    def reserve(index: int) -> tuple[str, float]:
        key = f"api-{index}"
        barrier.wait(timeout=5)
        reservation = budget._reserve(key, current_time=0.0, not_before=0.0)
        return key, reservation.scheduled_at

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(reserve, range(workers)))

    assert len({key for key, _scheduled_at in results}) == workers
    assert {scheduled_at for _key, scheduled_at in results} == {0.0}


def test_concurrent_release_is_idempotent_and_does_not_remove_other_reservations() -> None:
    budget = RetryBudget(max_retries=3, per=10.0)
    reservations = [
        budget._reserve("api", current_time=0.0, not_before=float(index)) for index in range(3)
    ]
    workers = 12
    barrier = Barrier(workers)

    def release(index: int) -> None:
        barrier.wait(timeout=5)
        budget._release(reservations[index % len(reservations)])

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(release, range(workers)))

    replacement = budget._reserve("api", current_time=0.0, not_before=0.0)

    assert replacement.scheduled_at == 0.0


def test_concurrent_snapshots_are_individually_consistent() -> None:
    budget = RetryBudget(max_retries=4, per=2.0)
    for index in range(10):
        budget._reserve("api", current_time=0.0, not_before=index * 0.25)

    workers = 16
    barrier = Barrier(workers)

    def snapshot(_: int) -> tuple[int, int, int, float]:
        barrier.wait(timeout=5)
        current = budget.snapshot("api")
        return current.active, current.queued, current.available, current.next_available_in

    with ThreadPoolExecutor(max_workers=workers) as executor:
        snapshots = list(executor.map(snapshot, range(workers)))

    for active, queued, available, next_available_in in snapshots:
        assert 0 <= active <= budget.max_retries
        assert queued >= 0
        assert 0 <= available <= budget.max_retries
        assert next_available_in >= 0.0
