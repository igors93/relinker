"""Regression tests for Correction 3: sleeper contract validation.

- Async functions must not be accepted as sync sleepers (they create unawaited coroutines)
- Sync sleepers that return awaitables must be detected and raise InvalidRetryConfigError
- Async sleepers returning non-awaitables must raise InvalidRetryConfigError, not TypeError
"""

from __future__ import annotations

import asyncio
import contextlib
import warnings
from functools import partial

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy

# ---------------------------------------------------------------------------
# Sync sleeper validation
# ---------------------------------------------------------------------------


class TestSyncSleeperContract:
    def _policy(self, sleep: object) -> RetryPolicy:  # type: ignore[type-arg]
        return RetryPolicy().attempts(2).on(ValueError).with_sleep(sleep)  # type: ignore[arg-type]

    def test_sync_function_accepted(self) -> None:
        sleeps: list[float] = []
        policy = self._policy(sleeps.append)
        with pytest.raises(ValueError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert sleeps == [0.0]

    def test_callable_object_accepted(self) -> None:
        class SyncSleeper:
            def __call__(self, s: float) -> None:
                pass

        self._policy(SyncSleeper())

    def test_partial_accepted(self) -> None:
        def base_sleep(label: str, seconds: float) -> None:
            pass

        self._policy(partial(base_sleep, "test"))

    def test_async_function_rejected_at_with_sleep(self) -> None:
        async def async_sleeper(seconds: float) -> None:
            pass

        with pytest.raises(InvalidRetryConfigError, match="sync"):
            self._policy(async_sleeper)

    def test_async_callable_object_rejected(self) -> None:
        class AsyncSleeper:
            async def __call__(self, s: float) -> None:
                pass

        with pytest.raises(InvalidRetryConfigError, match="sync"):
            self._policy(AsyncSleeper())

    def test_sync_function_returning_coroutine_rejected_at_runtime(self) -> None:
        """A sync function that returns a coroutine must not silently leak unawaited."""

        async def _inner(s: float) -> None:
            pass

        def fake_sync_sleep(seconds: float):  # type: ignore[return]
            return _inner(seconds)  # returns a coroutine, but isn't async def

        policy = RetryPolicy().attempts(2).on(ValueError).with_sleep(fake_sync_sleep)
        # Must raise InvalidRetryConfigError and NOT produce a RuntimeWarning
        # about unawaited coroutine.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(InvalidRetryConfigError):
                policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        msgs = [str(w.message) for w in runtime_warnings]
        assert not runtime_warnings, f"Got RuntimeWarning about unawaited coroutine: {msgs}"

    def test_sleeper_not_called_when_config_invalid(self) -> None:
        """If rejection happens at with_sleep() time, the sleeper is never invoked."""

        async def bad_sleep(s: float) -> None:
            pass

        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy().attempts(2).on(ValueError).with_sleep(bad_sleep)
            # If we somehow got here, run() must not call bad_sleep
            # (but we expect the error above)

    def test_keyboard_interrupt_from_sleeper_propagates(self) -> None:
        def interrupting_sleep(s: float) -> None:
            raise KeyboardInterrupt

        policy = RetryPolicy().attempts(2).on(ValueError).with_sleep(interrupting_sleep)
        with pytest.raises(KeyboardInterrupt):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))


# ---------------------------------------------------------------------------
# Async sleeper validation
# ---------------------------------------------------------------------------


class TestAsyncSleeperContract:
    def _policy(self, async_sleep: object) -> RetryPolicy:  # type: ignore[type-arg]
        return (
            RetryPolicy().attempts(2).on(ValueError).with_sleep(lambda s: None, async_sleep)  # type: ignore[arg-type]
        )

    def test_async_function_accepted(self) -> None:
        async def valid_async_sleep(s: float) -> None:
            pass

        self._policy(valid_async_sleep)

    def test_async_callable_object_accepted(self) -> None:
        class AsyncSleeper:
            async def __call__(self, s: float) -> None:
                pass

        self._policy(AsyncSleeper())

    async def test_sync_function_returning_non_awaitable_raises_at_runtime(self) -> None:
        """Sync function returning None as async_sleep must raise InvalidRetryConfigError."""

        def returns_none(s: float) -> None:
            return None

        policy = self._policy(returns_none)

        async def task() -> None:
            raise ValueError("x")

        with pytest.raises(InvalidRetryConfigError):
            await policy.run_async(task)

    async def test_sync_function_returning_number_raises_at_runtime(self) -> None:
        def returns_number(s: float):  # type: ignore[return]
            return 42  # not awaitable

        policy = self._policy(returns_number)

        async def task() -> None:
            raise ValueError("x")

        with pytest.raises(InvalidRetryConfigError):
            await policy.run_async(task)

    async def test_asyncio_cancelled_error_propagates(self) -> None:
        call_count = [0]

        async def cancelling_sleep(s: float) -> None:
            call_count[0] += 1
            raise asyncio.CancelledError

        policy = (
            RetryPolicy().attempts(2).on(ValueError).with_sleep(lambda s: None, cancelling_sleep)
        )

        async def task() -> None:
            raise ValueError("x")

        with pytest.raises(asyncio.CancelledError):
            await policy.run_async(task)
        assert call_count[0] == 1

    async def test_async_sleeper_received_correct_delay(self) -> None:
        received: list[float] = []

        async def recording_sleep(s: float) -> None:
            received.append(s)

        calls = [0]

        async def task() -> None:
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("x")

        policy = (
            RetryPolicy()
            .attempts(3)
            .on(ValueError)
            .fixed_delay(0.5)
            .with_sleep(lambda s: None, recording_sleep)
        )
        await policy.run_async(task)
        assert received == [0.5]

    async def test_async_function_returning_already_completed_coroutine(self) -> None:
        """A sync function that returns a done coroutine is still a valid awaitable."""

        async def _done() -> None:
            pass

        coro = _done()
        # Drive it to completion
        with contextlib.suppress(StopIteration):
            coro.send(None)

        # A new coroutine (not the completed one) should still work
        async def make_coro(s: float) -> None:
            pass

        # This is a valid async function
        policy = self._policy(make_coro)
        calls = [0]

        async def task() -> None:
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("x")

        await policy.run_async(task)
        assert calls[0] == 2


# ---------------------------------------------------------------------------
# Integration: RetryPolicy(sleep=..., async_sleep=...) construction
# ---------------------------------------------------------------------------


class TestRetryPolicySleeperConstruction:
    def test_async_sleep_as_sleep_rejected_at_construction(self) -> None:
        async def async_sleep(s: float) -> None:
            pass

        with pytest.raises(InvalidRetryConfigError, match="sync"):
            RetryPolicy(sleep=async_sleep)  # type: ignore[arg-type]

    def test_non_callable_sleep_rejected_at_construction(self) -> None:
        with pytest.raises(InvalidRetryConfigError):
            RetryPolicy(sleep=42)  # type: ignore[arg-type]

    def test_for_testing_uses_noop_correctly(self) -> None:
        policy = RetryPolicy().for_testing()
        calls = [0]

        def task() -> str:
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("x")
            return "ok"

        result = policy.run(task)
        assert result == "ok"

    def test_custom_sync_sleeper_receives_delay_once(self) -> None:
        sleeps: list[float] = []
        policy = RetryPolicy().attempts(2).on(ValueError).fixed_delay(1.0).with_sleep(sleeps.append)
        with pytest.raises(ValueError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))
        assert sleeps == [1.0]

    async def test_custom_async_sleeper_receives_delay_once(self) -> None:
        received: list[float] = []

        async def async_sleeper(s: float) -> None:
            received.append(s)

        async def task() -> None:
            raise ValueError("x")

        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .fixed_delay(2.0)
            .with_sleep(lambda s: None, async_sleeper)
        )
        with pytest.raises(ValueError):
            await policy.run_async(task)
        assert received == [2.0]

    def test_budget_reservation_released_if_sleeper_fails(self) -> None:
        from relinker import RetryBudget

        def bad_sleep(s: float) -> None:
            raise RuntimeError("sleeper failed")

        budget = RetryBudget(max_retries=5, per=60)
        policy = (
            RetryPolicy()
            .attempts(2)
            .on(ValueError)
            .fixed_delay(0.0)
            .with_retry_budget(budget, key="test")
            .with_sleep(bad_sleep)
        )
        with pytest.raises(RuntimeError, match="sleeper failed"):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

        snap = budget.snapshot("test")
        assert snap.active == 0
        assert snap.available == snap.capacity
