"""
Tests for Retry-After safety cap (Correction 7).

Verifies that parse_retry_after caps huge numeric values, handles edge cases
correctly, and that MAX_RETRY_AFTER_SECONDS is accessible from the public API.
"""

from __future__ import annotations

import time

import pytest

from relinker.exceptions import InvalidRetryConfigError
from relinker.http import MAX_RETRY_AFTER_SECONDS, parse_retry_after


class TestParseRetryAfterBasic:
    def test_valid_integer_seconds(self) -> None:
        assert parse_retry_after("30") == 30.0

    def test_whitespace_stripped(self) -> None:
        assert parse_retry_after("  10  ") == 10.0

    def test_zero_seconds(self) -> None:
        assert parse_retry_after("0") == 0.0

    def test_default_when_empty(self) -> None:
        assert parse_retry_after("", default=5.0) == 5.0

    def test_default_when_invalid(self) -> None:
        assert parse_retry_after("not-a-number", default=3.0) == 3.0

    def test_negative_default_raises(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            parse_retry_after("bad", default=-5.0)


class TestParseRetryAfterNegative:
    def test_negative_numeric_returns_default(self) -> None:
        result = parse_retry_after("-10", default=2.0)
        assert result == 2.0

    def test_negative_zero_as_string(self) -> None:
        # "-0" is numerically 0, which is non-negative — returns 0.0
        result = parse_retry_after("-0", default=1.0)
        assert result == 0.0


class TestParseRetryAfterHugeValue:
    def test_huge_numeric_value_is_capped(self) -> None:
        result = parse_retry_after("999999999")
        assert result == MAX_RETRY_AFTER_SECONDS

    def test_huge_integer_conversion_safety(self) -> None:
        very_large = "9" * 50
        result = parse_retry_after(very_large)
        assert result == MAX_RETRY_AFTER_SECONDS

    def test_max_constant_is_one_day(self) -> None:
        assert MAX_RETRY_AFTER_SECONDS == 86400.0

    def test_custom_maximum_applied(self) -> None:
        result = parse_retry_after("3600", maximum=300.0)
        assert result == 300.0

    def test_value_below_maximum_is_not_capped(self) -> None:
        result = parse_retry_after("60", maximum=300.0)
        assert result == 60.0


class TestParseRetryAfterHTTPDate:
    def test_past_http_date_returns_zero(self) -> None:
        past_date = "Thu, 01 Jan 2000 00:00:00 GMT"
        result = parse_retry_after(past_date)
        assert result == 0.0

    def test_future_http_date_returns_positive_delay(self) -> None:
        future_ts = time.time() + 30.0
        future_struct = time.gmtime(future_ts)
        future_str = time.strftime("%a, %d %b %Y %H:%M:%S GMT", future_struct)
        result = parse_retry_after(future_str)
        assert 0.0 < result <= 31.0

    def test_invalid_date_returns_default(self) -> None:
        result = parse_retry_after("Thu, 99 Foo 2999 25:99:99 GMT", default=5.0)
        assert result == 5.0


class TestParseRetryAfterPublicAPI:
    def test_max_retry_after_seconds_importable(self) -> None:
        from relinker import MAX_RETRY_AFTER_SECONDS as public_max

        assert public_max == 86400.0
