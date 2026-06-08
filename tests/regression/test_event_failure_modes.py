"""Regression contracts for event handler failure modes."""

from __future__ import annotations

import logging

import pytest

from relinker import InvalidRetryConfigError, RetryBudget, RetryPolicy
from relinker.event import RetryEvent
from tests.contracts._support import FakeClock, patch_sync_clock


def test_event_handler_default_failure_mode_propagates_and_stops_later_handlers() -> None:
    calls: list[str] = []

    def fail(_: RetryEvent) -> None:
        calls.append("fail")
        raise RuntimeError("critical")

    def later(_: RetryEvent) -> None:
        calls.append("later")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .on_event("before_sleep", fail)
        .on_event("before_sleep", later)
    )

    def operation() -> None:
        raise TimeoutError("temporary")

    with pytest.raises(RuntimeError, match="critical"):
        policy.run(operation)

    assert calls == ["fail"]


def test_event_handler_rejects_invalid_failure_mode() -> None:
    with pytest.raises(InvalidRetryConfigError, match="failure_mode"):
        RetryPolicy().on_event(
            "before_sleep",
            lambda event: None,
            failure_mode="ignore",  # type: ignore[arg-type]
        )


def test_isolated_event_handler_failure_is_reported_and_later_handlers_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls: list[str] = []

    def fail(_: RetryEvent) -> None:
        calls.append("fail")
        raise RuntimeError("secret-token-123")

    def later(_: RetryEvent) -> None:
        calls.append("later")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .on_event("before_sleep", fail, failure_mode="isolate")
        .on_event("before_sleep", later)
    )
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary")
        return "ok"

    with caplog.at_level(logging.WARNING, logger="relinker.events"):
        assert policy.run(operation) == "ok"

    assert calls == ["fail", "later"]
    assert attempts == 2
    log_text = caplog.text
    assert "RuntimeError" in log_text
    assert "before_sleep" in log_text
    assert "secret-token-123" not in log_text


def test_isolated_event_handler_does_not_capture_base_exception() -> None:
    def interrupt(_: RetryEvent) -> None:
        raise KeyboardInterrupt

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .on_event("before_sleep", interrupt, failure_mode="isolate")
    )

    def operation() -> None:
        raise TimeoutError("temporary")

    with pytest.raises(KeyboardInterrupt):
        policy.run(operation)


def test_isolated_before_sleep_failure_keeps_budget_reservation_for_retry() -> None:
    budget = RetryBudget(max_retries=1, per=10)
    calls = 0

    def observer(_: RetryEvent) -> None:
        raise RuntimeError("metric sink down")

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .with_retry_budget(budget, key="api")
        .on_event("before_sleep", observer, failure_mode="isolate")
        .with_sleep(lambda _: None)
    )

    assert policy.run(operation) == "ok"
    assert calls == 2
    assert budget._reservations != {}


def test_isolated_before_sleep_handler_time_is_still_counted_against_max_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    patch_sync_clock(monkeypatch, clock)
    sleeps: list[float] = []
    calls = 0

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        clock.sleep(delay)

    def observer(_: RetryEvent) -> None:
        clock.value = 4.5
        raise RuntimeError("metric sink down")

    def operation() -> str:
        nonlocal calls
        calls += 1
        raise TimeoutError("temporary")

    policy = (
        RetryPolicy()
        .attempts(3)
        .max_time(5.0)
        .on(TimeoutError)
        .fixed_delay(1.0)
        .on_event("before_sleep", observer, failure_mode="isolate")
        .with_sleep(sleep)
        .return_result()
    )

    result = policy.run(operation)

    assert result.exhausted
    assert calls == 1
    assert sleeps == []


def test_logging_built_in_handler_failure_is_isolated(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("tests.relinker.failing")

    def fail_log(*_: object, **__: object) -> None:
        raise RuntimeError("sink secret")

    monkeypatch.setattr(logger, "log", fail_log)
    policy = RetryPolicy().attempts(2).on(TimeoutError).fixed_delay(0).with_logging(logger=logger)
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return "ok"

    with caplog.at_level(logging.WARNING, logger="relinker.events"):
        assert policy.run(operation) == "ok"

    assert calls == 2
    assert "RuntimeError" in caplog.text
    assert "sink secret" not in caplog.text


def test_isolated_failure_reporter_failure_does_not_recurse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_logger = logging.getLogger("relinker.events")

    def fail_report(*_: object, **__: object) -> None:
        raise RuntimeError("reporter down")

    monkeypatch.setattr(event_logger, "warning", fail_report)
    calls: list[str] = []

    def fail(_: RetryEvent) -> None:
        calls.append("fail")
        raise RuntimeError("observer down")

    def later(_: RetryEvent) -> None:
        calls.append("later")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fixed_delay(0)
        .on_event("before_sleep", fail, failure_mode="isolate")
        .on_event("before_sleep", later)
    )
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary")
        return "ok"

    assert policy.run(operation) == "ok"
    assert calls == ["fail", "later"]
