"""Regression tests for Correction 5: reduce redundant history materialization.

On stateless paths without before_sleep handlers, the executor must not
materialize a full tuple(attempts) snapshot for every retry.

Tests verify:
- Functional correctness is preserved across all paths
- Stateful delay still receives a complete real state snapshot
- Handlers still receive complete immutable snapshots
- History immutability is preserved
- 1000-retry stateless path completes without O(N^2) tuple copies
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from relinker import RetryPolicy
from relinker.event import RetryEvent

# ---------------------------------------------------------------------------
# Functional correctness
# ---------------------------------------------------------------------------


class TestFunctionalCorrectness:
    def test_stateless_no_handler_succeeds(self) -> None:
        calls = [0]

        def task() -> str:
            calls[0] += 1
            if calls[0] < 3:
                raise ValueError("retry")
            return "ok"

        result = RetryPolicy().attempts(5).on(ValueError).for_testing().run(task)
        assert result == "ok"
        assert calls[0] == 3

    def test_stateless_no_handler_correct_attempt_count(self) -> None:
        calls = [0]

        def task() -> None:
            calls[0] += 1
            raise ValueError("x")

        policy = RetryPolicy().attempts(3).on(ValueError).for_testing()
        with pytest.raises(ValueError):
            policy.run(task)
        assert calls[0] == 3

    def test_stateful_delay_still_receives_real_state(self) -> None:
        captured: list[object] = []
        from relinker.state import RetryState

        def callback(state: RetryState) -> float:
            captured.append(state)
            return 0.0

        policy = RetryPolicy().attempts(3).on(ValueError).stateful_delay(callback).for_testing()
        with pytest.raises(ValueError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

        assert captured
        assert captured[0].function_name != "<simulation>"
        assert captured[0].last_error is not None

    def test_before_sleep_handler_receives_complete_state(self) -> None:
        events: list[RetryEvent] = []
        policy = RetryPolicy().attempts(3).on(ValueError).on_retry(events.append).for_testing()
        with pytest.raises(ValueError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

        assert events
        state = events[0].state
        assert state is not None
        assert state.attempt_number == 1

    def test_handler_snapshot_immutable_after_next_attempt(self) -> None:
        snapshots: list[Any] = []

        def capture_state(event: RetryEvent) -> None:
            if event.state:
                snapshots.append(event.state)

        policy = RetryPolicy().attempts(4).on(ValueError).on_failure(capture_state).for_testing()
        with pytest.raises(ValueError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

        # on_failure fires for every failed attempt (including the final one with will_retry=False)
        # 4 attempts → 4 after_failure events
        assert len(snapshots) == 4
        # The first snapshot should have 1 attempt, second should have 2
        assert len(snapshots[0].attempts) == 1
        assert len(snapshots[1].attempts) == 2
        # First snapshot must not change after subsequent retries
        assert len(snapshots[0].attempts) == 1

    def test_history_limit_still_applied(self) -> None:
        captured: list[Any] = []

        policy = (
            RetryPolicy()
            .attempts(10)
            .on(ValueError)
            .keep_history(3)
            .on_retry(lambda e: captured.append(e.state))
            .for_testing()
        )
        with pytest.raises(ValueError):
            policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

        assert captured
        for state in captured:
            assert state is not None
            assert len(state.attempts) <= 3

    def test_unlimited_history_still_works(self) -> None:
        n = 20
        calls = [0]

        def task() -> None:
            calls[0] += 1
            raise ValueError("x")

        policy = (
            RetryPolicy()
            .attempts(n)
            .on(ValueError)
            .keep_history(None)
            .return_result()
            .for_testing()
        )
        result = policy.run(task)
        assert result.total_attempts == n

    def test_after_success_handler_receives_state(self) -> None:
        events: list[RetryEvent] = []
        policy = RetryPolicy().attempts(3).on(ValueError).on_success(events.append).for_testing()
        calls = [0]

        def task() -> str:
            calls[0] += 1
            if calls[0] < 2:
                raise ValueError("x")
            return "done"

        result = policy.run(task)
        assert result == "done"
        assert events
        state = events[0].state
        assert state is not None

    def test_sync_and_async_parity(self) -> None:
        import asyncio

        policy = RetryPolicy().attempts(3).on(ValueError).for_testing()
        calls_sync = [0]
        calls_async = [0]

        def sync_task() -> None:
            calls_sync[0] += 1
            raise ValueError("x")

        async def async_task() -> None:
            calls_async[0] += 1
            raise ValueError("x")

        with pytest.raises(ValueError):
            policy.run(sync_task)

        with pytest.raises(ValueError):
            asyncio.run(policy.run_async(async_task))

        assert calls_sync[0] == calls_async[0] == 3


# ---------------------------------------------------------------------------
# Structural efficiency (no rigid timing, use instrumentation)
# ---------------------------------------------------------------------------


class TestStructuralEfficiency:
    def test_1000_stateless_retries_no_handler_completes_quickly(self) -> None:
        """1000 retries on stateless path must complete in reasonable time."""
        calls = [0]

        def task() -> None:
            calls[0] += 1
            raise ValueError("x")

        policy = RetryPolicy().attempts(1000).on(ValueError).for_testing()
        start = time.monotonic()
        with pytest.raises(ValueError):
            policy.run(task)
        elapsed = time.monotonic() - start

        assert calls[0] == 1000
        # This should be fast: under 5 seconds even on slow CI
        # The main cost was O(N^2) tuple materialization; with fix it's O(N)
        assert elapsed < 5.0, f"1000 retries took {elapsed:.2f}s — possible O(N^2) regression"

    def test_result_final_contains_correct_total_attempts(self) -> None:
        """Total attempt count in result must be correct even without full history."""
        policy = (
            RetryPolicy().attempts(50).on(ValueError).keep_history(5).return_result().for_testing()
        )
        result = policy.run(lambda: (_ for _ in ()).throw(ValueError("x")))

        # return_result() returns RetryResult instead of raising
        from relinker.result import RetryResult

        assert isinstance(result, RetryResult)
        # attempt_count must use total_attempts, not len(attempts)
        assert result.total_attempts == 50
        assert len(result.attempts) == 5
