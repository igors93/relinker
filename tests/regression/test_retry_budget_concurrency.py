"""Concurrent RetryBudget invariants."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

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


def test_concurrent_snapshots_observe_populated_state_with_controlled_clock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budget = RetryBudget(max_retries=4, per=2.0)
    controlled_time = 100.0
    monkeypatch.setattr("relinker.budget._monotonic", lambda: controlled_time)

    budget._reserve("api", current_time=controlled_time, not_before=controlled_time)
    released_future = budget._reserve(
        "api",
        current_time=controlled_time,
        not_before=controlled_time + 0.25,
    )
    budget._release(released_future)
    budget._reserve(
        "api",
        current_time=controlled_time,
        not_before=controlled_time + 0.5,
    )

    baseline = budget.snapshot("api")
    assert baseline.active == 1
    assert baseline.queued == 1
    assert 0 <= baseline.available <= budget.max_retries
    assert baseline.next_available_in >= 0.0

    readers = 16
    writers = 8
    workers = readers + writers
    barrier = Barrier(workers)

    def snapshot(_: int) -> tuple[int, int, int, float]:
        barrier.wait(timeout=5)
        current = budget.snapshot("api")
        return current.active, current.queued, current.available, current.next_available_in

    def reserve_future(index: int) -> None:
        barrier.wait(timeout=5)
        budget._reserve(
            "api",
            current_time=controlled_time,
            not_before=controlled_time + 0.75 + index * 0.01,
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        snapshot_futures = [executor.submit(snapshot, index) for index in range(readers)]
        writer_futures = [executor.submit(reserve_future, index) for index in range(writers)]
        snapshots = [future.result() for future in snapshot_futures]
        for future in writer_futures:
            future.result()

    for active, queued, available, next_available_in in snapshots:
        assert active == 1
        assert queued >= 1
        assert 0 <= available <= budget.max_retries
        assert next_available_in >= 0.0

    final_snapshot = budget.snapshot("api")
    assert final_snapshot.active == 1
    assert final_snapshot.queued >= 1 + writers
