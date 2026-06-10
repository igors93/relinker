"""Shared deterministic pieces of retry executor flow."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

from relinker.event import RetryEvent
from relinker.internal.retry_wait import RetryWaitPlan
from relinker.state import RetryState

if TYPE_CHECKING:
    from relinker.internal.runtime import RetryRuntime
    from relinker.policy import RetryPolicy


def state_with_wait_plan(state: RetryState, plan: RetryWaitPlan) -> RetryState:
    """Return ``state`` annotated with the resolved wait plan."""
    return replace(
        state,
        next_delay=plan.total_delay,
        policy_delay=plan.policy_delay,
        budget_delay=plan.budget_delay,
    )


def record_failure_and_emit(
    policy: RetryPolicy[Any],
    runtime: RetryRuntime,
    *,
    attempt_started_at: float,
    attempt_ended_at: float,
    error: Exception,
    should_retry: bool,
) -> bool:
    """Record one failed attempt, emit after_failure, and return should_stop."""
    runtime.record_failure(
        started_at=attempt_started_at,
        ended_at=attempt_ended_at,
        error=error,
    )
    elapsed = attempt_ended_at - runtime.started_at
    should_stop = policy.stop_strategy.should_stop(runtime.attempt_number, elapsed)

    policy.emit(
        RetryEvent(
            name="after_failure",
            attempt_number=runtime.attempt_number,
            function_name=runtime.function_name,
            error=error,
            state=runtime.state(
                last_error=error,
                retry_cause="exception",
                will_retry=should_retry and not should_stop,
                will_stop=should_stop,
            )
            if policy._has_handler("after_failure")
            else None,
        )
    )
    return should_stop
