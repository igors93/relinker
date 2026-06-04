"""Tests for the dependency-free HTTP helpers."""

from __future__ import annotations

from retryflow.http import (
    parse_retry_after,
    retry_after_delay,
    retry_if_status,
    should_retry_http_status,
)


def test_should_retry_http_status_in_set() -> None:
    assert should_retry_http_status(503, {500, 502, 503, 504}) is True


def test_should_retry_http_status_not_in_set() -> None:
    assert should_retry_http_status(200, {500, 502, 503, 504}) is False


def test_should_retry_http_status_empty_set() -> None:
    assert should_retry_http_status(500, set()) is False


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


def test_retry_after_delay_returns_constant() -> None:
    delay_fn = retry_after_delay(default=2.0)
    assert delay_fn(1) == 2.0
    assert delay_fn(10) == 2.0


def test_retry_after_delay_with_maximum() -> None:
    delay_fn = retry_after_delay(default=100.0, maximum=30.0)
    assert delay_fn(1) == 30.0


def test_retry_after_delay_maximum_larger_than_default() -> None:
    delay_fn = retry_after_delay(default=5.0, maximum=60.0)
    assert delay_fn(1) == 5.0


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


def test_parse_retry_after_http_date() -> None:
    import time

    # A future HTTP date should return a positive delay
    future = time.gmtime(time.time() + 300)
    http_date = time.strftime("%a, %d %b %Y %H:%M:%S GMT", future)
    result = parse_retry_after(http_date, default=0.0)
    # Allow some tolerance for the clock
    assert 250 < result < 350


def test_retry_if_status_list_input() -> None:
    predicate = retry_if_status([500, 502, 503])
    assert predicate(FakeResponse(502)) is True
    assert predicate(FakeResponse(200)) is False


def test_parse_retry_after_float_string_falls_back_to_default() -> None:
    # "1.5" cannot be parsed as int, and is not a valid HTTP date,
    # so it should fall back to the default.
    assert parse_retry_after("1.5", default=5.0) == 5.0


def test_parse_retry_after_whitespace_only_falls_back() -> None:
    assert parse_retry_after("   ", default=3.0) == 3.0


def test_parse_retry_after_none_like_string_falls_back() -> None:
    assert parse_retry_after("None", default=2.0) == 2.0


def test_retry_if_status_callable_returns_callable() -> None:
    predicate = retry_if_status({503})
    assert callable(predicate)


def test_should_retry_http_status_accepts_generator() -> None:
    # Iterable should work, not just sets
    gen = (s for s in [500, 503])
    assert should_retry_http_status(503, gen) is True


def test_retry_if_status_empty_set_always_false() -> None:
    predicate = retry_if_status(set())
    assert predicate(FakeResponse(500)) is False
    assert predicate({"status_code": 500}) is False


def test_retry_after_delay_zero_default() -> None:
    delay_fn = retry_after_delay(default=0.0)
    assert delay_fn(1) == 0.0
    assert delay_fn(99) == 0.0
