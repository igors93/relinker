"""Regression tests for event name validation in RetryPolicy.on_event()."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.event import RetryEvent


def test_on_event_rejects_unknown_event_name() -> None:
    def handler(event: RetryEvent) -> None:
        pass

    # Typo validation
    with pytest.raises(InvalidRetryConfigError, match="unknown event name 'after_sucess'"):
        RetryPolicy().on_event("after_sucess", handler)  # type: ignore[arg-type]

    # Totally invalid name validation
    with pytest.raises(InvalidRetryConfigError, match="unknown event name 'not_an_event'"):
        RetryPolicy().on_event("not_an_event", handler)  # type: ignore[arg-type]


def test_on_event_rejects_non_string_event_name() -> None:
    def handler(event: RetryEvent) -> None:
        pass

    # None validation
    with pytest.raises(InvalidRetryConfigError, match="unknown event name None"):
        RetryPolicy().on_event(None, handler)  # type: ignore[arg-type]

    # Integer validation
    with pytest.raises(InvalidRetryConfigError, match="unknown event name 42"):
        RetryPolicy().on_event(42, handler)  # type: ignore[arg-type]


def test_on_event_accepts_all_valid_event_names() -> None:
    def handler(event: RetryEvent) -> None:
        pass

    for name in (
        "before_attempt",
        "after_success",
        "after_failure",
        "before_sleep",
        "after_giveup",
    ):
        policy = RetryPolicy().on_event(name, handler)  # type: ignore[arg-type]
        assert len(policy.event_handlers) == 1
        assert policy.event_handlers[0].name == name


def test_on_event_aliases_continue_to_work() -> None:
    def handler(event: RetryEvent) -> None:
        pass

    policy = (
        RetryPolicy()
        .on_before_attempt(handler)
        .on_success(handler)
        .on_failure(handler)
        .on_retry(handler)
        .on_giveup(handler)
    )

    names = [h.name for h in policy.event_handlers]
    assert names == [
        "before_attempt",
        "after_success",
        "after_failure",
        "before_sleep",
        "after_giveup",
    ]
