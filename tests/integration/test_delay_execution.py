"""Integration tests for observable delay execution behavior."""

from __future__ import annotations

from relinker import RetryPolicy


def test_fixed_delay_is_used_before_each_additional_attempt() -> None:
    sleeps: list[float] = []
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(1.25).with_sleep(sleeps.append)
    assert policy.run(operation) == "ok"
    assert sleeps == [1.25, 1.25]


def test_linear_delay_sequence_and_cap_are_observable_through_sleep() -> None:
    sleeps: list[float] = []
    policy = (
        RetryPolicy()
        .attempts(5)
        .on(TimeoutError)
        .linear_delay(start=1, step=2, maximum=5)
        .with_sleep(sleeps.append)
        .return_result()
    )
    result = policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert result.exhausted is True
    assert sleeps == [1, 3, 5, 5]


def test_exponential_delay_sequence_and_cap_are_observable_through_sleep() -> None:
    sleeps: list[float] = []
    policy = (
        RetryPolicy()
        .attempts(5)
        .on(TimeoutError)
        .exponential_delay(base=1, factor=2, maximum=5)
        .with_sleep(sleeps.append)
        .return_result()
    )
    policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert sleeps == [1, 2, 4, 5]


def test_chain_delay_reuses_last_value_after_sequence_ends() -> None:
    sleeps: list[float] = []
    policy = (
        RetryPolicy()
        .attempts(5)
        .on(TimeoutError)
        .chain_delay([0.1, 0.5])
        .with_sleep(sleeps.append)
        .return_result()
    )
    policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert sleeps == [0.1, 0.5, 0.5, 0.5]


def test_custom_delay_receives_one_based_failed_attempt_number() -> None:
    seen: list[int] = []
    sleeps: list[float] = []

    def delay(attempt_number: int) -> float:
        seen.append(attempt_number)
        return float(attempt_number)

    policy = (
        RetryPolicy()
        .attempts(3)
        .on(TimeoutError)
        .custom_delay(delay)
        .with_sleep(sleeps.append)
        .return_result()
    )
    policy.run(lambda: (_ for _ in ()).throw(TimeoutError("down")))
    assert seen == [1, 2]
    assert sleeps == [1.0, 2.0]


def test_stateful_delay_receives_last_exception_and_retry_cause() -> None:
    observed: list[tuple[type[BaseException] | None, str | None]] = []

    def delay(state: object) -> float:
        last_error = state.last_error
        observed.append(
            (
                type(last_error) if last_error is not None else None,
                state.retry_cause,
            )
        )
        return 0

    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .stateful_delay(delay)
        .with_sleep(lambda _: None)
    )
    assert policy.run(operation) == "ok"
    assert observed == [(TimeoutError, "exception")]


def test_seeded_random_delay_is_repeatable_across_equivalent_policies() -> None:
    first = (
        RetryPolicy()
        .attempts(4)
        .random_delay(minimum=1, maximum=2, seed=42)
        .simulate(4)
    )
    second = (
        RetryPolicy()
        .attempts(4)
        .random_delay(minimum=1, maximum=2, seed=42)
        .simulate(4)
    )
    assert [item.delay_before_next_attempt for item in first.attempts] == [
        item.delay_before_next_attempt for item in second.attempts
    ]
