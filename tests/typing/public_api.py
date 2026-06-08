from typing import Any

from relinker import (
    RetryBudget,
    RetryPolicy,
    RetryResult,
    RetryState,
    RetryStats,
    RetryStatsSnapshot,
    RetryWrappedFunction,
    TryAgain,
)


def make_policy() -> RetryPolicy[int]:
    return RetryPolicy[int]().attempts(2)


def make_budget() -> RetryBudget:
    return RetryBudget(max_retries=1, per=60)


def accept_result(result: RetryResult[int]) -> int:
    if result.value is None:
        return 0
    return result.value


def accept_state(state: RetryState) -> int:
    return state.attempt_number


def accept_stats(stats: RetryStats) -> RetryStatsSnapshot:
    return stats.snapshot()


def accept_snapshot(snapshot: RetryStatsSnapshot) -> float:
    return snapshot.success_rate


def accept_wrapped(
    function: RetryWrappedFunction[..., object],
) -> RetryWrappedFunction[..., Any]:
    return function.with_policy(RetryPolicy[object]().attempts(1))


def make_try_again() -> TryAgain:
    return TryAgain("retry")
