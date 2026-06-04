from __future__ import annotations

import pytest

from retryflow.exceptions import InvalidRetryConfigError
from retryflow.http import (
    http_retry_policy,
    parse_retry_after,
    retry_after_delay,
    retry_if_status,
)
from retryflow.state import RetryState


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
