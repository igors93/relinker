"""
Regression tests for C3: validate default/maximum arguments in
parse_retry_after() and retry_after_delay() using ensure_non_negative.

NaN, inf, bool, and negative values must raise InvalidRetryConfigError.
"""

from __future__ import annotations

import pytest

from relinker.exceptions import InvalidRetryConfigError
from relinker.http import parse_retry_after, retry_after_delay

# ---------------------------------------------------------------------------
# parse_retry_after
# ---------------------------------------------------------------------------


class TestParseRetryAfterArgValidation:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1.0, -0.001])
    def test_bad_default_raises(self, bad: float) -> None:
        with pytest.raises(InvalidRetryConfigError):
            parse_retry_after("30", default=bad)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1.0])
    def test_bad_maximum_raises(self, bad: float) -> None:
        with pytest.raises(InvalidRetryConfigError):
            parse_retry_after("30", maximum=bad)

    def test_bool_default_raises(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            parse_retry_after("30", default=True)  # type: ignore[arg-type]

    def test_bool_maximum_raises(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            parse_retry_after("30", maximum=False)  # type: ignore[arg-type]

    def test_zero_default_accepted(self) -> None:
        assert parse_retry_after("30", default=0.0) == 30.0

    def test_zero_maximum_accepted(self) -> None:
        assert parse_retry_after("30", maximum=0.0) == 0.0

    def test_default_exceeding_maximum_is_capped(self) -> None:
        result = parse_retry_after("not-a-number", default=100.0, maximum=50.0)
        assert result == 50.0


# ---------------------------------------------------------------------------
# retry_after_delay
# ---------------------------------------------------------------------------


class TestRetryAfterDelayArgValidation:
    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1.0, -0.001])
    def test_bad_default_raises(self, bad: float) -> None:
        with pytest.raises(InvalidRetryConfigError):
            retry_after_delay(default=bad)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), -1.0])
    def test_bad_maximum_raises(self, bad: float) -> None:
        with pytest.raises(InvalidRetryConfigError):
            retry_after_delay(default=1.0, maximum=bad)

    def test_bool_default_raises(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            retry_after_delay(default=True)  # type: ignore[arg-type]

    def test_zero_default_accepted(self) -> None:
        fn = retry_after_delay(default=0.0)
        assert callable(fn)

    def test_valid_args_return_callable(self) -> None:
        fn = retry_after_delay(default=1.0, maximum=30.0)
        assert callable(fn)
