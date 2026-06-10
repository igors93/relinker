"""Tests for the with_logging() policy method."""

from __future__ import annotations

import logging

import pytest

from relinker import RetryPolicy


def test_with_logging_logs_before_sleep(caplog: pytest.LogCaptureFixture) -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise TimeoutError("timeout")
        return "ok"

    policy = (
        RetryPolicy()
        .attempts(5)
        .on(TimeoutError)
        .fixed_delay(0)
        .with_logging(level=logging.WARNING)
    )

    with caplog.at_level(logging.WARNING, logger="relinker"):
        policy.run(task)

    assert any("Attempt" in r.message and "retrying" in r.message for r in caplog.records)


def test_with_logging_logs_after_giveup(caplog: pytest.LogCaptureFixture) -> None:
    def task() -> str:
        raise TimeoutError("always")

    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(0).with_logging()

    with caplog.at_level(logging.WARNING, logger="relinker"), pytest.raises(TimeoutError):
        policy.run(task)

    assert any("Giving up" in r.message for r in caplog.records)


def test_with_logging_uses_custom_logger(caplog: pytest.LogCaptureFixture) -> None:
    custom_logger = logging.getLogger("my_app.retry")

    def task() -> str:
        raise ValueError("fail")

    policy = (
        RetryPolicy().attempts(2).on(ValueError).fixed_delay(0).with_logging(logger=custom_logger)
    )

    with caplog.at_level(logging.WARNING, logger="my_app.retry"), pytest.raises(ValueError):
        policy.run(task)

    assert any(r.name == "my_app.retry" for r in caplog.records)


def test_with_logging_uses_custom_level(caplog: pytest.LogCaptureFixture) -> None:
    def task() -> str:
        raise ValueError("fail")

    policy = (
        RetryPolicy().attempts(2).on(ValueError).fixed_delay(0).with_logging(level=logging.INFO)
    )

    with caplog.at_level(logging.INFO, logger="relinker"), pytest.raises(ValueError):
        policy.run(task)

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(info_records) > 0


def test_with_logging_does_not_log_success(caplog: pytest.LogCaptureFixture) -> None:
    def task() -> str:
        return "ok"

    policy = RetryPolicy().attempts(3).with_logging()

    with caplog.at_level(logging.WARNING, logger="relinker"):
        policy.run(task)

    assert len(caplog.records) == 0


def test_with_logging_returns_new_policy() -> None:
    policy = RetryPolicy().attempts(3)
    logged_policy = policy.with_logging()
    assert logged_policy is not policy
    assert len(logged_policy.event_handlers) > len(policy.event_handlers)


def test_with_logging_preserves_behavior() -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise TimeoutError("retry")
        return "done"

    policy = RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(0).with_logging()
    result = policy.run(task)

    assert result == "done"
    assert calls[0] == 3


def test_with_logging_result_rejection_giveup(caplog: pytest.LogCaptureFixture) -> None:
    policy = (
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda v: v == "bad")
        .fixed_delay(0)
        .raise_on_result_exhausted()
        .with_logging()
    )

    from relinker import RetryExhaustedError

    with caplog.at_level(logging.WARNING, logger="relinker"), pytest.raises(RetryExhaustedError):
        policy.run(lambda: "bad")

    giveup_records = [r for r in caplog.records if "Giving up" in r.message]
    assert len(giveup_records) > 0


def test_with_logging_sleep_log_contains_error_class(caplog: pytest.LogCaptureFixture) -> None:
    """The before_sleep log message should include the error class name."""

    def task() -> str:
        raise TimeoutError("timed out")

    policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(0).with_logging()

    with caplog.at_level(logging.WARNING, logger="relinker"), pytest.raises(TimeoutError):
        policy.run(task)

    sleep_records = [r for r in caplog.records if "retrying" in r.message]
    assert len(sleep_records) > 0
    assert any("TimeoutError" in r.message for r in sleep_records)


def test_with_logging_sleep_log_contains_delay(caplog: pytest.LogCaptureFixture) -> None:
    """The before_sleep log message should include the delay value."""

    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise TimeoutError("timed out")
        return "ok"

    policy = RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(0).with_logging()

    with caplog.at_level(logging.WARNING, logger="relinker"):
        policy.run(task)

    sleep_records = [r for r in caplog.records if "retrying" in r.message]
    assert len(sleep_records) > 0
    # Delay is 0.00 seconds
    assert any("0.00" in r.message for r in sleep_records)


def test_with_logging_giveup_message_contains_error_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The after_giveup log message includes error message when include_error_message=True."""

    def task() -> str:
        raise ValueError("bad argument")

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(ValueError)
        .fixed_delay(0)
        .with_logging(include_error_message=True)
    )

    with caplog.at_level(logging.WARNING, logger="relinker"), pytest.raises(ValueError):
        policy.run(task)

    giveup_records = [r for r in caplog.records if "Giving up" in r.message]
    assert len(giveup_records) > 0
    assert any("ValueError" in r.message for r in giveup_records)
    assert any("bad argument" in r.message for r in giveup_records)
