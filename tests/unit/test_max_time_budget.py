"""
Tests for max_time() as a real time budget (Correction 1).

Verifies that when a time-based stop condition is active, the executor does not
sleep beyond the remaining budget. Uses fake clocks and monkeypatching — no
real sleeps.
"""

from __future__ import annotations

import contextlib

from relinker import RetryPolicy
from relinker.exceptions import RetryExhaustedError
from relinker.internal.exhaustion import should_stop_before_sleep
from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.max_time import StopAfterDelay

# ---------------------------------------------------------------------------
# should_stop_before_sleep helper
# ---------------------------------------------------------------------------


class TestShouldStopBeforeSleep:
    def test_time_strategy_stops_when_delay_exceeds_budget(self) -> None:
        strategy = StopAfterDelay(1.0)
        # elapsed=0.9, delay=60 → elapsed+delay=60.9 > 1.0 → stop
        assert should_stop_before_sleep(strategy, 1, 0.9, 60.0) is True

    def test_time_strategy_does_not_stop_when_delay_fits(self) -> None:
        strategy = StopAfterDelay(10.0)
        # elapsed=0.5, delay=1.0 → elapsed+delay=1.5 < 10.0 → do not stop
        assert should_stop_before_sleep(strategy, 1, 0.5, 1.0) is False

    def test_attempt_only_strategy_does_not_trigger_early(self) -> None:
        strategy = StopAfterAttempt(5)
        # attempt=1, so no stop regardless of elapsed+delay
        assert should_stop_before_sleep(strategy, 1, 0.0, 60.0) is False

    def test_zero_delay_never_triggers_early(self) -> None:
        strategy = StopAfterDelay(1.0)
        assert should_stop_before_sleep(strategy, 1, 0.5, 0.0) is False


# ---------------------------------------------------------------------------
# Sync executor: max_time does not oversleep
# ---------------------------------------------------------------------------


class TestSyncMaxTimeDoesNotOversleep:
    def test_max_time_one_second_does_not_sleep_sixty_seconds(self) -> None:
        slept: list[float] = []

        def fake_sleep(seconds: float) -> None:
            slept.append(seconds)

        call_count = [0]

        def failing_function() -> None:
            call_count[0] += 1
            raise ValueError("fail")

        policy = RetryPolicy().max_time(0.001).fixed_delay(60.0).with_sleep(fake_sleep)

        with contextlib.suppress(ValueError, RetryExhaustedError):
            policy.run(failing_function)

        assert not slept, f"Expected no sleep, but got: {slept}"

    def test_attempt_policy_still_sleeps(self) -> None:
        slept: list[float] = []

        def fake_sleep(seconds: float) -> None:
            slept.append(seconds)

        call_count = [0]

        def failing_function() -> None:
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("fail")

        policy = RetryPolicy().attempts(3).fixed_delay(0.0).with_sleep(fake_sleep)
        policy.run(failing_function)
        # attempt-based policy should sleep normally
        assert len(slept) == 2

    def test_result_based_retry_does_not_oversleep(self) -> None:
        slept: list[float] = []

        def fake_sleep(seconds: float) -> None:
            slept.append(seconds)

        def always_bad() -> int:
            return -1

        policy = (
            RetryPolicy()
            .max_time(0.001)
            .fixed_delay(60.0)
            .retry_if_result(lambda v: v < 0)
            .with_sleep(fake_sleep)
        )

        with contextlib.suppress(RetryExhaustedError):
            policy.run(always_bad)

        assert not slept, f"Expected no sleep, but got: {slept}"


# ---------------------------------------------------------------------------
# Async executor: max_time does not oversleep
# ---------------------------------------------------------------------------


class TestAsyncMaxTimeDoesNotOversleep:
    async def test_async_max_time_does_not_sleep_sixty_seconds(self) -> None:
        slept: list[float] = []

        async def fake_async_sleep(seconds: float) -> None:
            slept.append(seconds)

        async def failing_function() -> None:
            raise ValueError("fail")

        policy = (
            RetryPolicy()
            .max_time(0.001)
            .fixed_delay(60.0)
            .with_sleep(lambda s: None, fake_async_sleep)
        )

        with contextlib.suppress(ValueError, RetryExhaustedError):
            await policy.run_async(failing_function)

        assert not slept, f"Expected no async sleep, but got: {slept}"

    async def test_async_result_based_does_not_oversleep(self) -> None:
        slept: list[float] = []

        async def fake_async_sleep(seconds: float) -> None:
            slept.append(seconds)

        async def always_bad() -> int:
            return -1

        policy = (
            RetryPolicy()
            .max_time(0.001)
            .fixed_delay(60.0)
            .retry_if_result(lambda v: v < 0)
            .with_sleep(lambda s: None, fake_async_sleep)
        )

        with contextlib.suppress(RetryExhaustedError):
            await policy.run_async(always_bad)

        assert not slept


# ---------------------------------------------------------------------------
# Sync context manager: max_time does not oversleep
# ---------------------------------------------------------------------------


class TestContextManagerMaxTimeDoesNotOversleep:
    def test_sync_context_manager_does_not_oversleep(self) -> None:
        slept: list[float] = []

        def fake_sleep(seconds: float) -> None:
            slept.append(seconds)

        policy = RetryPolicy().max_time(0.001).fixed_delay(60.0).with_sleep(fake_sleep)

        with contextlib.suppress(ValueError):
            for attempt in policy:
                with attempt:
                    raise ValueError("fail")

        assert not slept

    async def test_async_context_manager_does_not_oversleep(self) -> None:
        slept: list[float] = []

        async def fake_async_sleep(seconds: float) -> None:
            slept.append(seconds)

        policy = (
            RetryPolicy()
            .max_time(0.001)
            .fixed_delay(60.0)
            .with_sleep(lambda s: None, fake_async_sleep)
        )

        with contextlib.suppress(ValueError):
            async for attempt in policy:
                async with attempt:
                    raise ValueError("fail")

        assert not slept


# ---------------------------------------------------------------------------
# Event ordering: after_giveup must fire, before_sleep must NOT fire
# ---------------------------------------------------------------------------


class TestEventOrderingWhenBudgetExceeded:
    def test_no_before_sleep_when_stopping_early(self) -> None:
        events: list[str] = []

        def track(event: object) -> None:
            from relinker.event import RetryEvent

            if isinstance(event, RetryEvent):
                events.append(event.name)

        policy = (
            RetryPolicy()
            .max_time(0.001)
            .fixed_delay(60.0)
            .on_event("before_sleep", track)
            .on_event("after_giveup", track)
            .with_sleep(lambda s: None)
        )

        with contextlib.suppress(ValueError, RetryExhaustedError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("fail")))

        assert "before_sleep" not in events
        assert "after_giveup" in events
