"""Tests for the TryAgain explicit retry signal."""

from __future__ import annotations

import pytest

from relinker import RetryExhaustedError, RetryPolicy, TryAgain


def test_try_again_sync_then_succeeds() -> None:
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise TryAgain("not ready yet")
        return "done"

    result = RetryPolicy().attempts(5).return_result().run(task)

    assert result.succeeded
    assert result.value == "done"
    assert result.attempt_count == 3


def test_try_again_bypasses_condition_filter() -> None:
    """TryAgain should retry even when .on(SomeOtherError) is configured."""
    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise TryAgain("explicit retry")
        return "ok"

    result = (
        RetryPolicy()
        .attempts(5)
        .on(ValueError)  # TryAgain is NOT ValueError
        .return_result()
        .run(task)
    )

    assert result.succeeded
    assert result.value == "ok"
    assert result.attempt_count == 2


def test_try_again_exhaustion_with_return_result() -> None:
    def task() -> str:
        raise TryAgain("always retrying")

    result = RetryPolicy().attempts(3).return_result().run(task)

    assert result.failed
    assert result.exhausted
    assert result.attempt_count == 3
    assert isinstance(result.error, TryAgain)


def test_try_again_with_fallback() -> None:
    def task() -> str:
        raise TryAgain("always retrying")

    policy = RetryPolicy().attempts(3).fallback(lambda _: "fallback_value")
    value = policy.run(task)

    assert value == "fallback_value"


def test_try_again_preserves_message() -> None:
    message = "waiting for upstream"

    def task() -> str:
        raise TryAgain(message)

    result = RetryPolicy().attempts(2).return_result().run(task)

    assert isinstance(result.error, TryAgain)
    assert str(result.error) == message


def test_try_again_does_not_swallow_system_exit() -> None:
    """TryAgain handling must not prevent SystemExit from propagating."""

    def task() -> None:
        raise SystemExit(1)

    with pytest.raises(SystemExit):
        RetryPolicy().attempts(3).run(task)


def test_try_again_does_not_swallow_keyboard_interrupt() -> None:
    """TryAgain handling must not prevent KeyboardInterrupt from propagating."""

    def task() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        RetryPolicy().attempts(3).run(task)


def test_try_again_respects_stop_strategy() -> None:
    """TryAgain should still respect the attempt limit."""
    calls = [0]

    def task() -> str:
        calls[0] += 1
        raise TryAgain("retry")

    result = RetryPolicy().attempts(4).return_result().run(task)

    assert result.exhausted
    assert calls[0] == 4


@pytest.mark.asyncio
async def test_try_again_async_then_succeeds() -> None:
    calls = [0]

    async def task() -> str:
        calls[0] += 1
        if calls[0] < 3:
            raise TryAgain("not ready yet")
        return "async done"

    result = await RetryPolicy().attempts(5).return_result().run_async(task)

    assert result.succeeded
    assert result.value == "async done"
    assert result.attempt_count == 3


@pytest.mark.asyncio
async def test_try_again_async_exhaustion_with_return_result() -> None:
    async def task() -> str:
        raise TryAgain("always")

    result = await RetryPolicy().attempts(3).return_result().run_async(task)

    assert result.exhausted
    assert isinstance(result.error, TryAgain)


@pytest.mark.asyncio
async def test_try_again_async_with_fallback() -> None:
    async def task() -> str:
        raise TryAgain("retry")

    policy = RetryPolicy().attempts(3).fallback(lambda _: "async_fallback")
    value = await policy.run_async(task)

    assert value == "async_fallback"


def test_try_again_in_context_manager() -> None:
    calls = [0]

    policy = RetryPolicy().attempts(5).on(ValueError)  # TryAgain bypasses this
    for attempt in policy:
        with attempt:
            calls[0] += 1
            if calls[0] < 3:
                raise TryAgain("not ready")

    assert calls[0] == 3


def test_try_again_exhaustion_in_context_manager() -> None:
    """When TryAgain exhausts in a context manager, TryAgain propagates (consistent with
    how regular exceptions propagate on exhaustion in context managers)."""
    calls = [0]

    policy = RetryPolicy().attempts(3)
    with pytest.raises(TryAgain):
        for attempt in policy:
            with attempt:
                calls[0] += 1
                raise TryAgain("always retry")

    assert calls[0] == 3


def test_try_again_on_exhausted_raise() -> None:
    def task() -> str:
        raise TryAgain("retry")

    policy = RetryPolicy().attempts(3).on_exhausted_raise(RetryExhaustedError)
    with pytest.raises(RetryExhaustedError):
        policy.run(task)


def test_try_again_story_shows_error_class() -> None:
    """story() should mention TryAgain when the result was exhausted by TryAgain."""

    def task() -> str:
        raise TryAgain("polling")

    result = RetryPolicy().attempts(2).return_result().run(task)
    text = result.story()

    assert "TryAgain" in text
    assert "exhausted" in text


def test_try_again_last_error_in_result() -> None:
    """result.last_error should be the TryAgain instance when exhausted."""

    def task() -> str:
        raise TryAgain("not ready")

    result = RetryPolicy().attempts(3).return_result().run(task)

    assert isinstance(result.last_error, TryAgain)
    assert str(result.last_error) == "not ready"


def test_try_again_failed_attempts_count() -> None:
    """All attempts should be counted as failed when TryAgain is always raised."""
    calls = [0]

    def task() -> str:
        calls[0] += 1
        raise TryAgain("retry")

    result = RetryPolicy().attempts(4).return_result().run(task)

    assert result.failed_attempts == 4
    assert result.successful_attempts == 0
    assert result.attempt_count == 4


def test_try_again_with_custom_exhausted_exception_factory() -> None:
    """TryAgain exhaustion should respect on_exhausted_raise with a factory."""

    class JobNotReadyError(RuntimeError):
        pass

    def task() -> str:
        raise TryAgain("not ready")

    policy = (
        RetryPolicy()
        .attempts(3)
        .on_exhausted_raise(
            lambda r: JobNotReadyError(f"exhausted after {r.attempt_count} attempts")
        )
    )
    with pytest.raises(JobNotReadyError, match="exhausted after 3 attempts"):
        policy.run(task)


def test_try_again_error_in_logs_via_with_logging(caplog: pytest.LogCaptureFixture) -> None:
    """with_logging should log TryAgain class name when it causes a retry."""
    import logging

    calls = [0]

    def task() -> str:
        calls[0] += 1
        if calls[0] < 2:
            raise TryAgain("not ready")
        return "ok"

    policy = RetryPolicy().attempts(5).fixed_delay(0).with_logging(level=logging.WARNING)

    with caplog.at_level(logging.WARNING, logger="relinker"):
        policy.run(task)

    assert any("TryAgain" in r.message for r in caplog.records)
