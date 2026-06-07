"""Regression contracts for decorated-function statistics under concurrency."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from relinker import RetryPolicy


def test_decorated_function_stats_count_concurrent_calls_once_each() -> None:
    workers = 8
    barrier = Barrier(workers)

    @RetryPolicy().attempts(1)
    def task(value: int) -> int:
        barrier.wait(timeout=5)
        return value

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(task, range(workers)))

    snapshot = task.retry_stats.snapshot()
    assert sorted(results) == list(range(workers))
    assert snapshot.calls == workers
    assert snapshot.successes == workers
    assert snapshot.failures == 0
    assert snapshot.exhausted == 0
    assert snapshot.total_attempts == workers
    assert snapshot.calls == snapshot.successes + snapshot.failures


def test_with_policy_uses_independent_statistics() -> None:
    @RetryPolicy().attempts(1)
    def task() -> str:
        return "ok"

    stricter = task.with_policy(RetryPolicy().attempts(1))

    assert task() == "ok"
    assert stricter() == "ok"

    assert task.retry_stats.snapshot().calls == 1
    assert stricter.retry_stats.snapshot().calls == 1
    assert task.retry_stats is not stricter.retry_stats
