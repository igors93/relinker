"""Integration tests for dependency-free HTTP retry helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from relinker import (
    MAX_RETRY_AFTER_SECONDS,
    http_retry_policy,
    parse_retry_after,
    retry_if_status,
    should_retry_http_status,
)


@dataclass
class Response:
    status_code: int
    headers: dict[str, str] | None = None


def _no_sleep(_: float) -> None:
    pass


def test_should_retry_http_status_uses_requested_collection() -> None:
    assert should_retry_http_status(503, {500, 503}) is True
    assert should_retry_http_status(404, {500, 503}) is False


def test_retry_if_status_supports_response_objects() -> None:
    predicate = retry_if_status({429, 503})
    assert predicate(Response(429)) is True
    assert predicate(Response(200)) is False


def test_retry_if_status_supports_dictionaries() -> None:
    predicate = retry_if_status({503})
    assert predicate({"status_code": 503}) is True
    assert predicate({"status_code": 200}) is False


def test_retry_if_status_accepts_objects_without_status_code() -> None:
    predicate = retry_if_status({503})
    assert predicate(object()) is False
    assert predicate({"other": 503}) is False


def test_parse_retry_after_accepts_whitespace_wrapped_seconds() -> None:
    assert parse_retry_after("  12  ") == 12.0


def test_parse_retry_after_negative_value_uses_default() -> None:
    assert parse_retry_after("-1", default=3) == 3.0


def test_parse_retry_after_caps_large_numeric_value() -> None:
    assert parse_retry_after("999999999") == MAX_RETRY_AFTER_SECONDS


def test_parse_retry_after_past_http_date_returns_zero() -> None:
    assert parse_retry_after("Sun, 06 Nov 1994 08:49:37 GMT") == 0.0


def test_http_policy_retries_status_then_accepts_success() -> None:
    responses = iter([Response(503), Response(200)])
    policy = http_retry_policy(attempts=2, respect_retry_after=False).with_sleep(_no_sleep)
    result = policy.return_result().run(lambda: next(responses))
    assert result.succeeded is True
    assert result.value.status_code == 200
    assert result.attempt_count == 2


def test_http_transport_exception_is_opt_in() -> None:
    calls = 0

    def operation() -> Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return Response(200)

    default_policy = http_retry_policy(attempts=2).with_sleep(_no_sleep)
    with pytest.raises(TimeoutError):
        default_policy.run(operation)
    assert calls == 1


def test_http_transport_exception_retries_when_configured() -> None:
    calls = 0

    def operation() -> Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return Response(200)

    policy = http_retry_policy(
        attempts=2,
        transport_exceptions=(TimeoutError,),
    ).with_sleep(_no_sleep)
    assert policy.run(operation).status_code == 200
    assert calls == 2


def test_http_retry_after_is_capped_by_policy_maximum_delay() -> None:
    sleeps: list[float] = []
    responses = iter([Response(429, {"Retry-After": "100"}), Response(200, {})])
    policy = http_retry_policy(
        attempts=2,
        default_delay=1,
        maximum_delay=5,
        respect_retry_after=True,
    ).with_sleep(sleeps.append)
    assert policy.run(lambda: next(responses)).status_code == 200
    assert sleeps == [5]
