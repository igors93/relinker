"""Executable versions of the primary examples shown in project documentation."""

from __future__ import annotations

import queue

from relinker import RetryBudget, RetryPolicy, TryAgain, retry


def test_basic_retry_decorator_example() -> None:
    calls = 0

    @retry(attempts=3, delay=0, on=(TimeoutError,))
    def fetch_data() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ready"

    assert fetch_data() == "ready"
    assert calls == 2


def test_fluent_policy_example() -> None:
    calls = 0

    def fetch_data() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionError("temporary")
        return "ready"

    policy = (
        RetryPolicy().attempts(3).on(TimeoutError, ConnectionError).fixed_delay(0).return_result()
    )

    result = policy.run(fetch_data)

    assert result.succeeded is True
    assert result.value == "ready"
    assert result.attempt_count == 2


def test_retry_budget_quick_start_example() -> None:
    calls = 0
    budget = RetryBudget(max_retries=2, per=60)

    def call_payments_api() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "paid"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError, ConnectionError)
        .fixed_delay(0)
        .with_retry_budget(budget, key="payments-api")
    )

    assert policy.run(call_payments_api) == "paid"
    assert calls == 2


def test_exhaustion_precedence_example() -> None:
    def fail() -> None:
        raise RuntimeError("boom")

    fallback_last = RetryPolicy().attempts(1).raise_last().fallback_value("safe")
    raise_last = RetryPolicy().attempts(1).fallback_value("safe").raise_last()

    assert fallback_last.run(fail) == "safe"

    try:
        raise_last.run(fail)
    except RuntimeError as error:
        assert str(error) == "boom"
    else:  # pragma: no cover - assertion guard
        raise AssertionError("raise_last() must re-raise the original exception")


def test_try_again_example() -> None:
    """TryAgain signals an explicit retry without matching the exception condition."""
    calls = 0

    def poll() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TryAgain(f"not ready on call {calls}")
        return "done"

    result = RetryPolicy().attempts(5).fixed_delay(0).run(poll)
    assert result == "done"
    assert calls == 3


def test_retry_if_result_example() -> None:
    """retry_if_result retries on returned values without raising exceptions."""
    calls = 0

    def poll() -> str:
        nonlocal calls
        calls += 1
        return "pending" if calls < 3 else "done"

    result = (
        RetryPolicy().attempts(5).retry_if_result(lambda v: v == "pending").fixed_delay(0).run(poll)
    )
    assert result == "done"
    assert calls == 3


def test_with_sleep_capture_example() -> None:
    """with_sleep lets tests capture requested sleep durations."""
    sleeps: list[float] = []
    calls = 0

    def fail_twice() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError()
        return "ok"

    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(5).with_sleep(sleeps.append)
    result = policy.run(fail_twice)
    assert result == "ok"
    assert sleeps == [5.0, 5.0]


def test_for_testing_no_sleep_example() -> None:
    """for_testing() removes real sleep and preserves all other policy settings."""
    calls = 0

    def fail_once() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return "ok"

    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(10).for_testing()
    result = policy.run(fail_once)
    assert result == "ok"
    assert calls == 2


def test_sync_event_handler_queues_events() -> None:
    """Sync event handlers can queue data for async consumers."""
    events: queue.Queue[dict] = queue.Queue()

    def record_retry(event) -> None:
        events.put_nowait({"attempt": event.attempt_number, "delay": event.delay})

    calls = 0

    def fail_once() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return "ok"

    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(0).on_retry(record_retry)
    result = policy.run(fail_once)
    assert result == "ok"
    assert not events.empty()
    entry = events.get_nowait()
    assert entry["attempt"] == 1


def test_generator_rejected_example() -> None:
    """Generator functions are rejected at call time with InvalidRetryConfigError."""
    from relinker import InvalidRetryConfigError

    def my_gen():  # type: ignore[return]
        yield 1

    policy = RetryPolicy().attempts(3)
    try:
        policy.run(my_gen)
    except InvalidRetryConfigError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Generator functions must raise InvalidRetryConfigError")


def test_async_handler_rejected_example() -> None:
    """Async event handlers are rejected at registration with InvalidRetryConfigError."""
    from relinker import InvalidRetryConfigError

    async def async_on_retry(event) -> None:
        pass

    try:
        RetryPolicy().attempts(3).on_retry(async_on_retry)
    except InvalidRetryConfigError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Async handlers must raise InvalidRetryConfigError")
