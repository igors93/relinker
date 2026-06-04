"""Tests for the dependency-free HTTP helpers."""

from __future__ import annotations

from retryflow.http import (
    _extract_retry_after_header,
    parse_retry_after,
    retry_after_delay,
    retry_if_status,
    should_retry_http_status,
)
from retryflow.state import RetryState

# -------------------------------------------------------- should_retry_http_status


def test_should_retry_http_status_in_set() -> None:
    assert should_retry_http_status(503, {500, 502, 503, 504}) is True


def test_should_retry_http_status_not_in_set() -> None:
    assert should_retry_http_status(200, {500, 502, 503, 504}) is False


def test_should_retry_http_status_empty_set() -> None:
    assert should_retry_http_status(500, set()) is False


def test_should_retry_http_status_accepts_generator() -> None:
    gen = (s for s in [500, 503])
    assert should_retry_http_status(503, gen) is True


# -------------------------------------------------------- retry_if_status


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_retry_if_status_with_attribute() -> None:
    predicate = retry_if_status({429, 503})
    assert predicate(FakeResponse(429)) is True
    assert predicate(FakeResponse(200)) is False


def test_retry_if_status_with_dict() -> None:
    predicate = retry_if_status({503})
    assert predicate({"status_code": 503}) is True
    assert predicate({"status_code": 200}) is False


def test_retry_if_status_unknown_object_returns_false() -> None:
    predicate = retry_if_status({503})
    assert predicate("not a response") is False
    assert predicate(42) is False
    assert predicate(None) is False
    assert predicate({}) is False


def test_retry_if_status_object_with_non_int_status_code() -> None:
    class WeirdResponse:
        status_code = "ok"

    predicate = retry_if_status({200})
    assert predicate(WeirdResponse()) is False


def test_retry_if_status_callable_returns_callable() -> None:
    predicate = retry_if_status({503})
    assert callable(predicate)


def test_retry_if_status_empty_set_always_false() -> None:
    predicate = retry_if_status(set())
    assert predicate(FakeResponse(500)) is False
    assert predicate({"status_code": 500}) is False


def test_retry_if_status_list_input() -> None:
    predicate = retry_if_status([500, 502, 503])
    assert predicate(FakeResponse(502)) is True
    assert predicate(FakeResponse(200)) is False


# -------------------------------------------------------- retry_after_delay (state-aware)


def _minimal_state(last_value: object = None) -> RetryState:
    """Build a minimal RetryState for unit testing the delay callback."""
    return RetryState(
        function_name="test",
        attempt_number=1,
        started_at=0.0,
        elapsed=0.0,
        last_value=last_value,
    )


def test_retry_after_delay_returns_callable() -> None:
    delay_fn = retry_after_delay(default=2.0)
    assert callable(delay_fn)


def test_retry_after_delay_default_when_no_response() -> None:
    delay_fn = retry_after_delay(default=2.0)
    state = _minimal_state(last_value=None)
    assert delay_fn(state) == 2.0


def test_retry_after_delay_default_when_no_header() -> None:
    delay_fn = retry_after_delay(default=3.0)

    class ResponseNoHeader:
        status_code = 429
        headers: dict[str, str] = {}

    state = _minimal_state(last_value=ResponseNoHeader())
    assert delay_fn(state) == 3.0


def test_retry_after_delay_reads_header_from_attribute() -> None:
    delay_fn = retry_after_delay(default=1.0)

    class Response:
        headers = {"Retry-After": "30"}

    state = _minimal_state(last_value=Response())
    assert delay_fn(state) == 30.0


def test_retry_after_delay_reads_header_from_dict() -> None:
    delay_fn = retry_after_delay(default=1.0)
    response = {"status_code": 429, "headers": {"Retry-After": "60"}}
    state = _minimal_state(last_value=response)
    assert delay_fn(state) == 60.0


def test_retry_after_delay_caps_at_maximum() -> None:
    delay_fn = retry_after_delay(default=1.0, maximum=10.0)

    class Response:
        headers = {"Retry-After": "120"}

    state = _minimal_state(last_value=Response())
    assert delay_fn(state) == 10.0


def test_retry_after_delay_maximum_larger_than_header() -> None:
    delay_fn = retry_after_delay(default=1.0, maximum=60.0)

    class Response:
        headers = {"Retry-After": "5"}

    state = _minimal_state(last_value=Response())
    assert delay_fn(state) == 5.0


def test_retry_after_delay_invalid_header_falls_back_to_default() -> None:
    delay_fn = retry_after_delay(default=2.0)

    class Response:
        headers = {"Retry-After": "not-a-number"}

    state = _minimal_state(last_value=Response())
    assert delay_fn(state) == 2.0


def test_retry_after_delay_never_negative() -> None:
    delay_fn = retry_after_delay(default=-5.0)
    state = _minimal_state(last_value=None)
    assert delay_fn(state) == 0.0


def test_retry_after_delay_case_insensitive_header() -> None:
    delay_fn = retry_after_delay(default=1.0)

    class Response:
        headers = {"retry-after": "45"}

    state = _minimal_state(last_value=Response())
    assert delay_fn(state) == 45.0


# --------------------------------------------------------- _extract_retry_after_header


def test_extract_from_attribute_headers() -> None:
    class Response:
        headers = {"Retry-After": "30"}

    assert _extract_retry_after_header(Response()) == "30"


def test_extract_from_dict_headers() -> None:
    response = {"headers": {"Retry-After": "60"}}
    assert _extract_retry_after_header(response) == "60"


def test_extract_missing_header_returns_none() -> None:
    class Response:
        headers: dict[str, str] = {}

    assert _extract_retry_after_header(Response()) is None


def test_extract_no_headers_attribute_returns_none() -> None:
    assert _extract_retry_after_header({"status_code": 429}) is None


def test_extract_none_response_returns_none() -> None:
    assert _extract_retry_after_header(None) is None


# -------------------------------------------------------- parse_retry_after


def test_parse_retry_after_integer() -> None:
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after("  60  ") == 60.0


def test_parse_retry_after_zero() -> None:
    assert parse_retry_after("0") == 0.0


def test_parse_retry_after_negative_clamped_to_zero() -> None:
    assert parse_retry_after("-5") == 0.0


def test_parse_retry_after_invalid_falls_back_to_default() -> None:
    assert parse_retry_after("not-a-date", default=5.0) == 5.0


def test_parse_retry_after_empty_falls_back_to_default() -> None:
    assert parse_retry_after("", default=3.0) == 3.0


def test_parse_retry_after_float_string_falls_back_to_default() -> None:
    assert parse_retry_after("1.5", default=5.0) == 5.0


def test_parse_retry_after_whitespace_only_falls_back() -> None:
    assert parse_retry_after("   ", default=3.0) == 3.0


def test_parse_retry_after_none_like_string_falls_back() -> None:
    assert parse_retry_after("None", default=2.0) == 2.0


def test_parse_retry_after_http_date() -> None:
    import time

    future = time.gmtime(time.time() + 300)
    http_date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", future)
    result = parse_retry_after(http_date, default=0.0)
    assert 250 < result < 350


# ------------------------------------------- full integration: retry + stateful delay


def test_retry_after_delay_integration_with_policy() -> None:
    """End-to-end: a result-based retry with a stateful Retry-After delay."""
    from retryflow import RetryPolicy

    responses = [
        {"status_code": 429, "headers": {"Retry-After": "0"}},
        {"status_code": 429, "headers": {"Retry-After": "0"}},
        {"status_code": 200},
    ]
    calls = [0]

    def fetch() -> dict[str, object]:
        resp = responses[calls[0]]
        calls[0] += 1
        return resp

    RETRYABLE = {429, 500, 503}

    policy = (
        RetryPolicy()
        .attempts(5)
        .retry_if_result(retry_if_status(RETRYABLE))
        .stateful_delay(retry_after_delay(default=0.0))
        .return_result()
    )

    result = policy.run(fetch)

    assert result.succeeded
    assert result.attempt_count == 3
    assert result.value == {"status_code": 200}
