"""Unit tests for the shared deterministic retry decisions (ADR 006)."""

from __future__ import annotations

from typing import Any

import pytest

import relinker.context
from relinker import RetryPolicy, TryAgain
from relinker.event import RetryEvent
from relinker.internal.executor_flow import FinalDecision, RetryFlow
from relinker.internal.retry_wait import RetryWaitPlan


def _flow(policy: RetryPolicy[Any]) -> RetryFlow:
    flow = RetryFlow(policy, function_name="task")
    flow.next_attempt()
    flow.enter_attempt()
    return flow


def test_accepted_value_is_final() -> None:
    decision = _flow(RetryPolicy()).after_value("ok")

    assert isinstance(decision, FinalDecision)
    assert decision.kind == "accept"
    assert decision.result.value == "ok"
    assert decision.result.succeeded


def test_non_retryable_exception_is_rejected() -> None:
    events: list[RetryEvent] = []
    policy = RetryPolicy().on(TimeoutError).on_giveup(events.append)
    error = ValueError("bad input")

    decision = _flow(policy).after_exception(error)

    assert isinstance(decision, FinalDecision)
    assert decision.kind == "reject"
    assert decision.result.error is error
    assert not decision.result.exhausted
    assert events[0].state is not None
    assert events[0].state.will_stop is False


def test_retryable_exception_with_attempts_left_plans_a_wait() -> None:
    events: list[RetryEvent] = []
    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(2).on_retry(events.append)

    decision = _flow(policy).after_exception(TimeoutError())

    assert isinstance(decision, RetryWaitPlan)
    assert decision.total_delay == 2.0
    assert events[0].delay == 2.0
    assert events[0].state is not None
    assert events[0].state.next_delay == 2.0


def test_retryable_exception_at_the_limit_is_exhausted() -> None:
    decision = _flow(RetryPolicy().attempts(1).on(TimeoutError)).after_exception(TimeoutError())

    assert isinstance(decision, FinalDecision)
    assert decision.kind == "exhaust"
    assert decision.result.exhausted_by_exception


def test_try_again_is_retried_even_when_the_condition_does_not_match() -> None:
    decision = _flow(RetryPolicy().attempts(2).on(TimeoutError)).after_exception(TryAgain())

    assert isinstance(decision, RetryWaitPlan)


def test_block_without_set_result_is_accepted_even_with_result_condition() -> None:
    policy = RetryPolicy().attempts(3).retry_if_result(lambda value: value is None)

    decision = _flow(policy).after_value(None, has_value=False)

    assert isinstance(decision, FinalDecision)
    assert decision.kind == "accept"


def test_rejected_value_at_the_limit_is_exhausted_by_result() -> None:
    policy = RetryPolicy().attempts(1).retry_if_result(lambda value: value == "wait")

    decision = _flow(policy).after_value("wait")

    assert isinstance(decision, FinalDecision)
    assert decision.result.exhausted_by_result


def test_state_snapshots_are_only_built_for_observed_events() -> None:
    flow = RetryFlow(RetryPolicy().attempts(1).on(TimeoutError), function_name="task")
    calls: list[dict[str, Any]] = []
    original_state = flow.runtime.state

    def counting_state(**fields: Any) -> Any:
        calls.append(fields)
        return original_state(**fields)

    flow.runtime.state = counting_state  # type: ignore[method-assign]
    flow.next_attempt()
    flow.enter_attempt()
    flow.after_exception(TimeoutError())

    assert calls == []


def test_runtime_clock_is_read_from_the_shared_clock_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticks = iter([100.0, 101.0, 103.5, 104.0, 104.0, 104.0])
    monkeypatch.setattr("relinker.internal.clock.now", lambda: next(ticks))

    flow = RetryFlow(RetryPolicy(), function_name="task")
    flow.next_attempt()
    flow.enter_attempt()
    decision = flow.after_value("ok")

    assert flow.runtime.started_at == 100.0
    assert flow.attempt_started_at == 101.0
    assert isinstance(decision, FinalDecision)
    assert decision.result.attempts[0].duration == 2.5


def test_retry_block_attempt_keeps_its_start_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("relinker.internal.clock.now", lambda: 42.0)
    iterator = RetryPolicy().attempts(1).iter()

    attempt = next(iterator)
    with attempt:
        pass

    assert attempt.attempt_started_at == 42.0


def test_context_package_no_longer_exposes_a_stale_clock_hook() -> None:
    # Patching relinker.context.now used to be required in tests; the single
    # patch point is now relinker.internal.clock.now.
    assert not hasattr(relinker.context, "now")


class _Shutdown(BaseException):
    """Stand-in for KeyboardInterrupt/SystemExit that pytest will not intercept."""


def test_retry_block_lets_base_exceptions_propagate_unrecorded() -> None:
    iterator = RetryPolicy().attempts(3).iter()

    with pytest.raises(_Shutdown):
        for attempt in iterator:
            with attempt:
                raise _Shutdown

    assert iterator.attempt_number == 1
    assert tuple(iterator.attempts) == ()
    assert iterator.finished is False


async def test_async_retry_block_lets_base_exceptions_propagate_unrecorded() -> None:
    iterator = RetryPolicy().attempts(3).async_iter()

    with pytest.raises(_Shutdown):
        async for attempt in iterator:
            async with attempt:
                raise _Shutdown

    assert tuple(iterator.attempts) == ()
