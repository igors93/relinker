from __future__ import annotations

import asyncio

import pytest

from relinker.exceptions import InvalidRetryConfigError
from relinker.http import (
    DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS,
    http_retry_policy,
    parse_retry_after,
    retry_after_delay,
    retry_if_status,
)
from relinker.state import RetryState


class Response:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None) -> None:
        self.status_code = status_code
        self.headers = headers or {}


def test_retry_if_status_matches_response_object() -> None:
    predicate = retry_if_status({429, 503})

    assert predicate(Response(429)) is True
    assert predicate(Response(200)) is False


def test_retry_after_delay_reads_header_from_state_value() -> None:
    callback = retry_after_delay(default=1.0, maximum=10.0)
    state = RetryState(
        function_name="test",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value=Response(429, {"Retry-After": "3"}),
    )

    assert callback(state) == 3.0


def test_parse_retry_after_rejects_large_untrusted_header() -> None:
    assert parse_retry_after("1" * 300, default=5.0) == 5.0


def test_http_retry_policy_validates_attempts() -> None:
    with pytest.raises(InvalidRetryConfigError):
        http_retry_policy(attempts=0)


def test_http_retry_policy_retries_configured_status_and_preserves_default_semantics() -> None:
    calls = 0
    sleeps: list[float] = []
    policy = http_retry_policy(statuses={503}, default_delay=0).with_sleep(sleeps.append)

    def call() -> Response:
        nonlocal calls
        calls += 1
        return Response(503 if calls == 1 else 200)

    result = policy.run(call)

    assert result.status_code == 200
    assert calls == 2
    assert sleeps == [0.0]


def test_http_retry_policy_does_not_retry_transport_error_by_default() -> None:
    calls = 0
    policy = http_retry_policy(statuses={503}, default_delay=0).for_testing()

    def call() -> Response:
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary")

    with pytest.raises(TimeoutError):
        policy.run(call)

    assert calls == 1


def test_http_retry_policy_retries_configured_transport_error() -> None:
    calls = 0
    sleeps: list[float] = []
    policy = http_retry_policy(
        statuses={503},
        transport_exceptions=(TimeoutError,),
        default_delay=1.5,
    ).with_sleep(sleeps.append)

    def call() -> Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return Response(200)

    result = policy.run(call)

    assert result.status_code == 200
    assert calls == 2
    assert sleeps == [1.5]


def test_http_retry_policy_combines_statuses_and_transport_errors() -> None:
    calls = 0
    sleeps: list[float] = []
    policy = http_retry_policy(
        statuses={503},
        transport_exceptions=(TimeoutError,),
        default_delay=0.25,
    ).with_sleep(sleeps.append)

    def call() -> Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response(503)
        if calls == 2:
            raise TimeoutError("temporary")
        return Response(200)

    result = policy.run(call)

    assert result.status_code == 200
    assert calls == 3
    assert sleeps == [0.25, 0.25]


def test_http_retry_policy_unconfigured_exception_propagates_immediately() -> None:
    calls = 0
    policy = http_retry_policy(
        statuses={503},
        transport_exceptions=(TimeoutError,),
        default_delay=0,
    ).for_testing()

    def call() -> Response:
        nonlocal calls
        calls += 1
        raise ValueError("not transport")

    with pytest.raises(ValueError, match="not transport"):
        policy.run(call)

    assert calls == 1


def test_http_retry_policy_status_uses_retry_after_and_transport_uses_default_delay() -> None:
    calls = 0
    sleeps: list[float] = []
    policy = http_retry_policy(
        statuses={503},
        transport_exceptions=(TimeoutError,),
        default_delay=2.0,
        maximum_delay=10.0,
    ).with_sleep(sleeps.append)

    def call() -> Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return Response(503, {"Retry-After": "7"})
        if calls == 2:
            raise TimeoutError("temporary")
        return Response(200)

    result = policy.run(call)

    assert result.status_code == 200
    assert sleeps == [7.0, 2.0]


@pytest.mark.asyncio
async def test_http_retry_policy_transport_error_async_parity() -> None:
    calls = 0
    sleeps: list[float] = []

    async def sleep(delay: float) -> None:
        sleeps.append(delay)
        await asyncio.sleep(0)

    policy = http_retry_policy(
        statuses={503},
        transport_exceptions=(TimeoutError,),
        default_delay=0.5,
    ).with_sleep(lambda _: None, sleep)

    async def call() -> Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return Response(200)

    result = await policy.run_async(call)

    assert result.status_code == 200
    assert calls == 2
    assert sleeps == [0.5]


def test_http_retry_policy_keyboard_interrupt_is_never_retried() -> None:
    calls = 0
    policy = http_retry_policy(
        transport_exceptions=DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS,
        default_delay=0,
    ).for_testing()

    def call() -> Response:
        nonlocal calls
        calls += 1
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        policy.run(call)

    assert calls == 1


@pytest.mark.parametrize(
    "transport_exceptions",
    [
        (object,),
        (BaseException,),
        (KeyboardInterrupt,),
        (SystemExit,),
        (TimeoutError, "TimeoutError"),
    ],
)
def test_http_retry_policy_validates_transport_exception_types(
    transport_exceptions: object,
) -> None:
    with pytest.raises(InvalidRetryConfigError):
        http_retry_policy(transport_exceptions=transport_exceptions)  # type: ignore[arg-type]
