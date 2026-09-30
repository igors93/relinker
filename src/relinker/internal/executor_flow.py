"""Shared deterministic retry decisions for executors and retry blocks.

Executors and retry-block context managers keep their own explicit loops: they
invoke the user callable, await it when needed, and perform the sleep. Every
decision taken between the end of an attempt and the next sleep is
deterministic and free of I/O, so it lives here once instead of being repeated
in each execution shape. See ADR 006.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Literal

from relinker.delays.stateful import delay_needs_state
from relinker.event import EventName, RetryEvent
from relinker.exceptions import TryAgain
from relinker.internal import clock
from relinker.internal.exhaustion import should_stop_before_sleep
from relinker.internal.retry_wait import RetryWaitPlan, plan_retry_wait, release_retry_wait
from relinker.internal.runtime import RetryRuntime

if TYPE_CHECKING:
    from relinker.policy import RetryPolicy
    from relinker.result import RetryResult
    from relinker.state import RetryCause, RetryState

FinalKind = Literal["accept", "reject", "exhaust"]


@dataclass(frozen=True, slots=True)
class FinalDecision:
    """Terminal outcome of one execution.

    ``accept``: the last value was accepted by the retry condition.
    ``reject``: a non-retryable exception ended the execution.
    ``exhaust``: the stop strategy or the retry budget ended retrying.
    """

    kind: FinalKind
    result: RetryResult[Any]


def state_with_wait_plan(state: RetryState, plan: RetryWaitPlan) -> RetryState:
    """Return ``state`` annotated with the resolved wait plan."""
    return replace(
        state,
        next_delay=plan.total_delay,
        policy_delay=plan.policy_delay,
        budget_delay=plan.budget_delay,
    )


class RetryFlow:
    """Decide what happens after each attempt of one retry execution.

    ``after_exception()`` and ``after_value()`` record the attempt, emit the
    matching events, and return either a ``RetryWaitPlan`` (sleep, then run
    another attempt) or a ``FinalDecision``. The caller owns the sleep and must
    call ``release_retry_wait(plan)`` when sleeping fails.
    """

    def __init__(self, policy: RetryPolicy[Any], *, function_name: str) -> None:
        self.policy = policy
        self.runtime = RetryRuntime(
            function_name=function_name,
            started_at=clock.now(),
            history_limit=policy.history_limit,
            policy_name=policy.name,
        )
        self._attempt_started_at = self.runtime.started_at

    @property
    def attempt_started_at(self) -> float:
        """Return the monotonic start time of the current attempt."""
        return self._attempt_started_at

    def next_attempt(self) -> int:
        """Start and return the next one-based attempt number."""
        return self.runtime.begin_attempt()

    def enter_attempt(self) -> None:
        """Emit ``before_attempt`` and start timing the current attempt."""
        self._emit("before_attempt")
        self._attempt_started_at = clock.now()

    def after_exception(self, error: Exception) -> RetryWaitPlan | FinalDecision:
        """Handle an attempt that raised ``error``."""
        policy = self.policy
        runtime = self.runtime
        should_retry = isinstance(error, TryAgain) or policy.condition.should_retry_exception(error)
        ended_at = clock.now()
        runtime.record_failure(
            started_at=self._attempt_started_at,
            ended_at=ended_at,
            error=error,
        )
        should_stop = policy.stop_strategy.should_stop(
            runtime.attempt_number, ended_at - runtime.started_at
        )
        self._emit(
            "after_failure",
            error=error,
            last_error=error,
            retry_cause="exception",
            will_retry=should_retry and not should_stop,
            will_stop=should_stop,
        )

        if not should_retry:
            result = runtime.result(ended_at=clock.now(), error=error)
            self._emit(
                "after_giveup",
                error=error,
                last_error=error,
                retry_cause="exception",
            )
            return FinalDecision("reject", result)

        if should_stop:
            return self._exhaust(error=error, retry_cause="exception")
        return self._plan_retry(error=error, retry_cause="exception")

    def after_value(self, value: Any, *, has_value: bool = True) -> RetryWaitPlan | FinalDecision:
        """Handle an attempt that completed without raising."""
        policy = self.policy
        runtime = self.runtime
        ended_at = clock.now()
        runtime.record_success(
            started_at=self._attempt_started_at,
            ended_at=ended_at,
            value=value,
            has_value=has_value,
        )
        should_retry = has_value and policy.condition.should_retry_result(value)
        should_stop = policy.stop_strategy.should_stop(
            runtime.attempt_number, ended_at - runtime.started_at
        )

        if not should_retry:
            result = runtime.result(ended_at=clock.now(), value=value)
            self._emit("after_success", value=value, last_value=value, has_value=has_value)
            return FinalDecision("accept", result)

        if should_stop:
            return self._exhaust(value=value, has_value=has_value, retry_cause="result")
        return self._plan_retry(value=value, has_value=has_value, retry_cause="result")

    # ------------------------------------------------------------ internals

    def _exhaust(
        self,
        *,
        retry_cause: RetryCause,
        value: Any = None,
        error: Exception | None = None,
        has_value: bool = False,
    ) -> FinalDecision:
        result = self.runtime.result(
            ended_at=clock.now(),
            value=value,
            error=error,
            exhausted=True,
            retry_cause=retry_cause,
        )
        self._emit(
            "after_giveup",
            value=value,
            error=error,
            last_value=value,
            last_error=error,
            has_value=has_value,
            retry_cause=retry_cause,
            will_stop=True,
        )
        return FinalDecision("exhaust", result)

    def _plan_retry(
        self,
        *,
        retry_cause: RetryCause,
        value: Any = None,
        error: Exception | None = None,
        has_value: bool = False,
    ) -> RetryWaitPlan | FinalDecision:
        policy = self.policy
        outcome: dict[str, Any] = {
            "value": value,
            "error": error,
            "has_value": has_value,
            "retry_cause": retry_cause,
        }
        pre_sleep_state = (
            self.runtime.state(
                last_value=value,
                last_error=error,
                has_value=has_value,
                retry_cause=retry_cause,
                will_retry=True,
            )
            if delay_needs_state(policy.delay_strategy) or policy._has_handler("before_sleep")
            else None
        )
        plan = plan_retry_wait(policy, self.runtime.attempt_number, pre_sleep_state)
        if plan is None:
            return self._exhaust(**outcome)
        if self._sleep_would_stop(plan):
            release_retry_wait(plan)
            return self._exhaust(**outcome)

        try:
            policy.emit(
                RetryEvent(
                    name="before_sleep",
                    attempt_number=self.runtime.attempt_number,
                    function_name=self.runtime.function_name,
                    delay=plan.total_delay,
                    value=value,
                    error=error,
                    state=state_with_wait_plan(pre_sleep_state, plan)
                    if pre_sleep_state is not None
                    else None,
                )
            )
        except BaseException:
            release_retry_wait(plan)
            raise

        # A before_sleep handler may consume part of a max_time budget.
        if self._sleep_would_stop(plan):
            release_retry_wait(plan)
            return self._exhaust(**outcome)
        return plan

    def _sleep_would_stop(self, plan: RetryWaitPlan) -> bool:
        return should_stop_before_sleep(
            self.policy.stop_strategy,
            self.runtime.attempt_number,
            clock.now() - self.runtime.started_at,
            plan.total_delay,
        )

    def _emit(
        self,
        name: EventName,
        *,
        value: Any = None,
        error: BaseException | None = None,
        **state_fields: Any,
    ) -> None:
        """Emit ``name``, building a state snapshot only when a handler observes it."""
        policy = self.policy
        runtime = self.runtime
        policy.emit(
            RetryEvent(
                name=name,
                attempt_number=runtime.attempt_number,
                function_name=runtime.function_name,
                value=value,
                error=error,
                state=runtime.state(**state_fields) if policy._has_handler(name) else None,
            )
        )
