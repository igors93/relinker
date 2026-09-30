"""Regression tests: malformed Retry-After headers never crash the retry loop.

Before the fix, ``parse_retry_after`` used ``str.lstrip("-").isdigit()``.
Values such as ``"--5"`` or ``"²"`` passed that check and then made ``int()``
raise ValueError, so a server sending ``Retry-After: --1`` crashed
``http_retry_policy()`` instead of falling back to the default delay.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from relinker import http_retry_policy, parse_retry_after
from relinker.http import MAX_RETRY_AFTER_SECONDS


@pytest.mark.parametrize(
    "header",
    [
        pytest.param("--5", id="double-minus"),
        pytest.param("-+5", id="mixed-signs"),
        pytest.param("+5", id="plus-sign"),
        pytest.param("²", id="superscript-two"),
        pytest.param("١٢", id="arabic-indic-digits"),
        pytest.param("５", id="fullwidth-digit"),
        pytest.param("5.5", id="decimal"),
        pytest.param("5 s", id="unit-suffix"),
    ],
)
def test_non_rfc_delay_seconds_fall_back_to_default(header: str) -> None:
    assert parse_retry_after(header, default=1.5) == 1.5


@pytest.mark.parametrize(
    ("header", "expected"),
    [("0", 0.0), ("-0", 0.0), ("7", 7.0), (" 42 ", 42.0), ("-3", 1.5)],
)
def test_ascii_delay_seconds_still_parse(header: str, expected: float) -> None:
    assert parse_retry_after(header, default=1.5) == expected


def test_huge_ascii_delay_is_capped() -> None:
    assert parse_retry_after("9" * 200, default=1.0) == MAX_RETRY_AFTER_SECONDS


@given(st.text(max_size=300))
def test_parse_retry_after_never_raises_for_arbitrary_text(header: str) -> None:
    delay = parse_retry_after(header, default=2.0)

    assert 0.0 <= delay <= MAX_RETRY_AFTER_SECONDS


class _Response:
    status_code = 503

    def __init__(self, retry_after: str) -> None:
        self.headers = {"Retry-After": retry_after}


@pytest.mark.parametrize("header", ["--1", "²"])
def test_http_policy_uses_default_delay_for_malformed_header(header: str) -> None:
    sleeps: list[float] = []
    policy = http_retry_policy(attempts=3, default_delay=0.25).with_sleep(sleeps.append)

    response = policy.run(lambda: _Response(header))

    assert response.status_code == 503  # result retry exhausted, last value returned
    assert sleeps == [0.25, 0.25]
