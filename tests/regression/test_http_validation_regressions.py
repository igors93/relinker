"""Regression tests for HTTP delay validation."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryState
from relinker.http import (
    MAX_RETRY_AFTER_SECONDS,
    http_retry_policy,
    parse_retry_after,
    retry_after_delay,
)


def test_retry_after_delay_rejects_default_above_safe_sleep_limit() -> None:
    with pytest.raises(InvalidRetryConfigError):
        retry_after_delay(default=90_000, maximum=None)


def test_retry_after_delay_accepts_default_at_safe_sleep_limit() -> None:
    callback = retry_after_delay(default=86_400, maximum=None)

    state = RetryState(
        function_name="request",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value={"headers": {}},
        has_value=True,
    )

    assert callback(state) == 86_400


def test_retry_after_delay_rejects_maximum_above_safe_sleep_limit() -> None:
    with pytest.raises(InvalidRetryConfigError):
        retry_after_delay(default=1.0, maximum=90_000)


def test_http_retry_policy_rejects_default_delay_above_safe_sleep_limit() -> None:
    with pytest.raises(InvalidRetryConfigError):
        http_retry_policy(
            respect_retry_after=True,
            default_delay=90_000,
        )


def test_http_retry_policy_rejects_maximum_delay_above_safe_sleep_limit() -> None:
    with pytest.raises(InvalidRetryConfigError):
        http_retry_policy(
            respect_retry_after=True,
            maximum_delay=90_000,
        )


def test_http_retry_policy_rejects_default_delay_above_limit_no_retry_after() -> None:
    with pytest.raises(InvalidRetryConfigError):
        http_retry_policy(
            respect_retry_after=False,
            default_delay=90_000,
        )


def test_parse_retry_after_still_caps_large_header_values() -> None:
    assert parse_retry_after("999999", default=1.0) == MAX_RETRY_AFTER_SECONDS


def test_retry_after_delay_returns_safe_default_when_header_is_absent() -> None:
    callback = retry_after_delay(default=2.5, maximum=10.0)

    state = RetryState(
        function_name="request",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value={"headers": {}},
        has_value=True,
    )

    assert callback(state) == 2.5
