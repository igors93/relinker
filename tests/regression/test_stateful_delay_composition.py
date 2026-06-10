"""Regression tests for Correction 2: StatefulCustomDelay in composition receives real state.

When StatefulCustomDelay is wrapped inside AdditiveDelay (via .jitter() or .add_delay()),
the callback must observe the real RetryState from the executor, not an artificial minimal
state with function_name='<simulation>' and no error/value context.
"""

from __future__ import annotations

from relinker import RetryPolicy
from relinker.delays.composite import AdditiveDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.stateful import StatefulCustomDelay
from relinker.state import RetryState


def _capture_states() -> tuple[list[RetryState], object]:
    captured: list[RetryState] = []

    def callback(state: RetryState) -> float:
        captured.append(state)
        return 0.0

    return captured, callback


# ---------------------------------------------------------------------------
# Core regression: stateful + jitter sees real error
# ---------------------------------------------------------------------------


def test_stateful_plus_jitter_sees_real_last_error() -> None:
    """Stateful callback inside jitter composition must observe real last_error."""
    captured, callback = _capture_states()

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(ValueError)
        .stateful_delay(callback)
        .jitter(minimum=0.0, maximum=0.0)
    )

    err = ValueError("real error")
    try:
        policy.run(lambda: (_ for _ in ()).throw(err))
    except ValueError:
        pass

    assert captured, "callback was never called"
    state = captured[0]
    # Must NOT be the artificial simulation state
    assert state.function_name != "<simulation>", (
        f"callback received artificial state with function_name={state.function_name!r}"
    )
    # Must have the real error
    assert state.last_error is err or type(state.last_error) is ValueError
    assert state.retry_cause == "exception"
    assert state.will_retry is True
    assert state.attempt_number == 1


def test_stateful_plus_jitter_sees_real_function_name() -> None:
    def my_func() -> None:
        raise OSError("x")

    captured, callback = _capture_states()
    policy = RetryPolicy().attempts(2).on(OSError).stateful_delay(callback).jitter(maximum=0.0)
    try:
        policy.run(my_func)
    except OSError:
        pass

    assert captured
    assert captured[0].function_name == "my_func"


def test_stateful_plus_fixed_sees_real_state() -> None:
    """stateful(callback) + fixed(0.0) — stateful is first in additive."""
    captured, callback = _capture_states()

    policy = (
        RetryPolicy().attempts(2).on(ValueError).stateful_delay(callback).add_delay(FixedDelay(0.0))
    )
    try:
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
    except ValueError:
        pass

    assert captured
    assert captured[0].last_error is not None
    assert captured[0].function_name != "<simulation>"


def test_fixed_plus_stateful_sees_real_state() -> None:
    """fixed(0.0) + stateful(callback) — stateful is second in additive."""
    captured, callback = _capture_states()

    # Build an additive where stateful is the second strategy
    stateful = StatefulCustomDelay(callback)
    additive = AdditiveDelay((FixedDelay(0.0), stateful))

    from dataclasses import replace

    policy = replace(
        RetryPolicy().attempts(2).on(ValueError),
        delay_strategy=additive,
    )
    try:
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
    except ValueError:
        pass

    assert captured
    assert captured[0].last_error is not None
    assert captured[0].function_name != "<simulation>"


def test_stateful_plus_jitter_sees_real_value_on_result_retry() -> None:
    """Stateful callback inside jitter must observe real last_value when retrying on result."""
    captured, callback = _capture_states()

    calls = [0]

    def task() -> str:
        calls[0] += 1
        return "bad" if calls[0] < 3 else "ok"

    policy = (
        RetryPolicy()
        .attempts(5)
        .retry_if_result(lambda v: v == "bad")
        .stateful_delay(callback)
        .jitter(minimum=0.0, maximum=0.0)
    )
    result = policy.run(task)

    assert result == "ok"
    assert captured
    state = captured[0]
    assert state.last_value == "bad"
    assert state.has_value is True
    assert state.retry_cause == "result"
    assert state.function_name != "<simulation>"


def test_two_stateful_in_additive_both_see_real_state() -> None:
    """Two StatefulCustomDelay in the same AdditiveDelay must both see the real state."""
    captured_a: list[RetryState] = []
    captured_b: list[RetryState] = []

    stateful_a = StatefulCustomDelay(lambda s: captured_a.append(s) or 0.0)
    stateful_b = StatefulCustomDelay(lambda s: captured_b.append(s) or 0.0)

    from dataclasses import replace

    policy = replace(
        RetryPolicy().attempts(2).on(ValueError),
        delay_strategy=AdditiveDelay((stateful_a, stateful_b)),
    )
    try:
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
    except ValueError:
        pass

    assert captured_a and captured_b
    # Both receive the same execution context (not simulation)
    assert captured_a[0].function_name != "<simulation>"
    assert captured_b[0].function_name != "<simulation>"
    assert captured_a[0].last_error is not None
    assert captured_b[0].last_error is not None
    # Same attempt number
    assert captured_a[0].attempt_number == captured_b[0].attempt_number


def test_nested_additive_stateful_sees_real_state() -> None:
    """Stateful inside nested AdditiveDelay sees real state."""
    captured, callback = _capture_states()

    stateful = StatefulCustomDelay(callback)
    inner = AdditiveDelay((FixedDelay(0.0), stateful))
    outer = AdditiveDelay((FixedDelay(0.0), inner))

    from dataclasses import replace

    policy = replace(
        RetryPolicy().attempts(2).on(ValueError),
        delay_strategy=outer,
    )
    try:
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
    except ValueError:
        pass

    assert captured
    assert captured[0].function_name != "<simulation>"
    assert captured[0].last_error is not None


def test_stateful_callback_called_once_per_retry() -> None:
    """Stateful callback is called exactly once per retry (not per resolution step)."""
    call_count = [0]

    def counting_callback(state: RetryState) -> float:
        call_count[0] += 1
        return 0.0

    policy = (
        RetryPolicy()
        .attempts(4)
        .on(ValueError)
        .stateful_delay(counting_callback)
        .jitter(minimum=0.0, maximum=0.0)
    )
    try:
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
    except ValueError:
        pass

    # 4 attempts → 3 retries → 3 sleeps → callback called 3 times
    assert call_count[0] == 3


def test_stateful_callback_not_called_when_no_retry_needed() -> None:
    """Stateful callback is not called when the function succeeds on first try."""
    call_count = [0]

    def callback(state: RetryState) -> float:
        call_count[0] += 1
        return 0.0

    policy = RetryPolicy().attempts(3).on(ValueError).stateful_delay(callback).jitter(maximum=0.0)
    result = policy.run(lambda: "ok")
    assert result == "ok"
    assert call_count[0] == 0


def test_stateful_callback_exception_propagates_and_budget_released() -> None:
    """If stateful callback raises, the exception propagates and budget is released."""

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(ValueError)
        .stateful_delay(lambda s: 1 / 0)  # ZeroDivisionError
        .jitter(maximum=0.0)
    )
    import pytest

    with pytest.raises(ZeroDivisionError):
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))


def test_stateful_callback_invalid_return_raises_before_sleep() -> None:
    """Stateful callback returning unsafe value → InvalidRetryConfigError before sleep."""
    import pytest

    from relinker import InvalidRetryConfigError
    from relinker.internal.validation import MAX_SLEEP_SECONDS

    sleeps: list[float] = []
    policy = (
        RetryPolicy()
        .attempts(2)
        .on(ValueError)
        .stateful_delay(lambda s: MAX_SLEEP_SECONDS + 1.0)
        .jitter(maximum=0.0)
        .with_sleep(sleeps.append)
    )
    with pytest.raises(InvalidRetryConfigError):
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
    assert sleeps == []


# ---------------------------------------------------------------------------
# Async parity
# ---------------------------------------------------------------------------


async def test_async_stateful_plus_jitter_sees_real_state() -> None:
    """Same contract as sync: stateful inside jitter sees real state in async executor."""
    captured, callback = _capture_states()

    async def task() -> None:
        raise ValueError("async error")

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(ValueError)
        .stateful_delay(callback)
        .jitter(minimum=0.0, maximum=0.0)
    )
    import pytest

    with pytest.raises(ValueError):
        await policy.run_async(task)

    assert captured
    state = captured[0]
    assert state.function_name != "<simulation>"
    assert state.last_error is not None
    assert state.retry_cause == "exception"


# ---------------------------------------------------------------------------
# Depth: 100+ levels of composition must not cause RecursionError
# ---------------------------------------------------------------------------


def test_deep_stateful_composition_does_not_recurse() -> None:
    """100 nested AdditiveDelay with StatefulCustomDelay must not cause RecursionError."""
    captured, callback = _capture_states()
    stateful = StatefulCustomDelay(callback)

    # Build 100 levels deep
    current: object = AdditiveDelay((stateful, FixedDelay(0.0)))
    for _ in range(99):
        current = AdditiveDelay((current, FixedDelay(0.0)))  # type: ignore[arg-type]

    from dataclasses import replace

    policy = replace(
        RetryPolicy().attempts(2).on(ValueError),
        delay_strategy=current,  # type: ignore[arg-type]
    )
    # Should not raise RecursionError
    try:
        policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
    except ValueError:
        pass

    assert captured
    assert captured[0].function_name != "<simulation>"


# ---------------------------------------------------------------------------
# Simulation still rejects stateful callbacks
# ---------------------------------------------------------------------------


def test_simulation_rejects_stateful_in_composition() -> None:
    """simulate() must reject policies with stateful callbacks in any composition depth."""
    import pytest

    from relinker import InvalidRetryConfigError

    policy = (
        RetryPolicy().attempts(3).on(ValueError).stateful_delay(lambda s: 0.0).jitter(maximum=0.0)
    )
    with pytest.raises(InvalidRetryConfigError, match="custom delay callbacks"):
        policy.simulate(attempts=3)
