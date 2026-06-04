"""Tests for state-aware delay (stateful_delay) and StatefulCustomDelay."""

from __future__ import annotations

import pytest

from relinker import RetryPolicy, RetryState
from relinker.delays.fixed import FixedDelay
from relinker.delays.stateful import StatefulCustomDelay, resolve_delay
from relinker.exceptions import InvalidRetryConfigError

# ----------------------------------------------------------------- basic API


def test_stateful_delay_receives_attempt_number() -> None:
    seen: list[int] = []

    def callback(state: RetryState) -> float:
        seen.append(state.attempt_number)
        return 0.0

    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise ValueError("retry me")
        return "ok"

    RetryPolicy().attempts(5).on(ValueError).stateful_delay(callback).run(task)

    assert seen == [1, 2]  # delay called after attempts 1 and 2


def test_stateful_delay_receives_last_error() -> None:
    seen_errors: list[type[BaseException] | None] = []

    def callback(state: RetryState) -> float:
        seen_errors.append(type(state.last_error) if state.last_error else None)
        return 0.0

    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise TimeoutError("timed out")
        return "ok"

    RetryPolicy().attempts(5).on(TimeoutError).stateful_delay(callback).run(task)

    assert seen_errors == [TimeoutError, TimeoutError]


def test_stateful_delay_receives_last_value_for_result_retry() -> None:
    seen_values: list[object] = []

    def callback(state: RetryState) -> float:
        seen_values.append(state.last_value)
        return 0.0

    responses = iter(["pending", "pending", "done"])

    policy = (
        RetryPolicy().attempts(5).retry_if_result(lambda v: v != "done").stateful_delay(callback)
    )

    policy.run(lambda: next(responses))

    assert seen_values == ["pending", "pending"]


def test_stateful_delay_sync() -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise OSError("retry")
        return "ok"

    policy = RetryPolicy().attempts(5).on(OSError).stateful_delay(lambda s: 0.0).return_result()
    result = policy.run(task)

    assert result.succeeded
    assert result.attempt_count == 3


@pytest.mark.asyncio
async def test_stateful_delay_async() -> None:
    calls = [0]

    async def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise OSError("retry")
        return "ok"

    policy = RetryPolicy().attempts(5).on(OSError).stateful_delay(lambda s: 0.0).return_result()
    result = await policy.run_async(task)

    assert result.succeeded
    assert result.attempt_count == 3


def test_stateful_delay_rejects_negative_return() -> None:
    def bad_callback(state: RetryState) -> float:
        return -1.0

    calls = [0]

    def task() -> str:
        calls[0] += 1
        raise ValueError("retry")

    policy = RetryPolicy().attempts(5).on(ValueError).stateful_delay(bad_callback)

    with pytest.raises(InvalidRetryConfigError, match="negative"):
        policy.run(task)


def test_stateful_delay_zero_is_valid() -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise ValueError("retry")
        return "ok"

    result = RetryPolicy().attempts(5).on(ValueError).stateful_delay(lambda s: 0.0).run(task)
    assert result == "ok"


def test_stateful_delay_can_vary_by_attempt() -> None:
    delays_used: list[float] = []

    def variable_delay(state: RetryState) -> float:
        d = float(state.attempt_number) * 0.0
        delays_used.append(float(state.attempt_number))
        return d

    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 4:
            raise ValueError("retry")
        return "ok"

    RetryPolicy().attempts(5).on(ValueError).stateful_delay(variable_delay).run(task)

    assert delays_used == [1.0, 2.0, 3.0]


# ------------------------------------------------ existing delays unaffected


def test_old_custom_delay_still_works() -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise ValueError("retry")
        return "ok"

    result = RetryPolicy().attempts(5).on(ValueError).custom_delay(lambda n: 0.0).run(task)
    assert result == "ok"


def test_fixed_delay_still_works() -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise ValueError("retry")
        return "ok"

    result = RetryPolicy().attempts(5).on(ValueError).fixed_delay(0).run(task)
    assert result == "ok"


def test_exponential_delay_still_works() -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise ValueError("retry")
        return "ok"

    policy = RetryPolicy().attempts(5).on(ValueError).exponential_delay(base=0.0001, factor=1)
    result = policy.run(task)
    assert result == "ok"


# ------------------------------------------- resolve_delay unit tests


def test_resolve_delay_uses_attempt_number_for_regular_strategy() -> None:
    from relinker.state import RetryState

    strategy = FixedDelay(2.0)
    state = RetryState(
        function_name="test",
        attempt_number=3,
        started_at=0.0,
        elapsed=0.0,
    )
    assert resolve_delay(strategy, 3, state) == 2.0


def test_resolve_delay_uses_state_for_stateful_strategy() -> None:
    from relinker.state import RetryState

    received: list[RetryState] = []

    def callback(s: RetryState) -> float:
        received.append(s)
        return 5.0

    strategy = StatefulCustomDelay(callback)
    state = RetryState(
        function_name="test",
        attempt_number=2,
        started_at=0.0,
        elapsed=1.0,
        last_error=ValueError("err"),
    )
    result = resolve_delay(strategy, 2, state)

    assert result == 5.0
    assert len(received) == 1
    assert received[0].last_error is state.last_error


# ---------------------------------------------- simulation with stateful delay


def test_stateful_delay_simulation_uses_attempt_number() -> None:
    def callback(state: RetryState) -> float:
        return float(state.attempt_number)

    policy = RetryPolicy().attempts(4).stateful_delay(callback)
    sim = policy.simulate(attempts=4)

    # Last attempt has delay 0 because stop fires there
    assert sim.attempts[0].delay_before_next_attempt == 1.0
    assert sim.attempts[1].delay_before_next_attempt == 2.0
    assert sim.attempts[2].delay_before_next_attempt == 3.0


# ---------------------------------------------- state fields in before_sleep event


def test_stateful_delay_state_visible_in_before_sleep_event() -> None:
    seen_states: list[RetryState | None] = []

    def on_sleep(event: object) -> None:
        from relinker.event import RetryEvent

        if isinstance(event, RetryEvent) and event.name == "before_sleep":
            seen_states.append(event.state)

    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise ValueError("retry")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(5)
        .on(ValueError)
        .stateful_delay(lambda s: 0.0)
        .on_event("before_sleep", on_sleep)
    )
    policy.run(task)

    assert len(seen_states) == 1
    state = seen_states[0]
    assert state is not None
    assert state.next_delay == 0.0
    assert state.will_retry is True


# ------------------------------------------ context manager with stateful delay


def test_stateful_delay_in_context_manager() -> None:
    seen: list[int] = []

    def callback(state: RetryState) -> float:
        seen.append(state.attempt_number)
        return 0.0

    calls = [0]
    policy = RetryPolicy().attempts(5).on(ValueError).stateful_delay(callback)

    for attempt in policy:
        with attempt:
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("retry")

    assert seen == [1, 2]
