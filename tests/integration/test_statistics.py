from typing import Any

from relinker import RetryPolicy


def test_decorated_function_collects_success_statistics() -> None:
    calls = {"count": 0}

    @RetryPolicy().attempts(3).on(RuntimeError)
    def task() -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return "ok"

    assert task() == "ok"

    stats: Any = task.retry_stats.to_dict()

    assert stats["calls"] == 1
    assert stats["successes"] == 1
    assert stats["failures"] == 0
    assert stats["total_attempts"] == 2


def test_decorated_function_collects_failure_statistics() -> None:
    @RetryPolicy().attempts(2).on(RuntimeError).return_result()
    def task() -> str:
        raise RuntimeError("temporary")

    result = task()
    stats: Any = task.retry_stats.snapshot()

    assert result.failed
    assert stats.calls == 1
    assert stats.failures == 1
    assert stats.exhausted == 1
    assert stats.total_attempts == 2
