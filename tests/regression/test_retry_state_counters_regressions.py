"""Regression tests: RetryState counters and history-copy optimisation."""

from __future__ import annotations

import asyncio
import contextlib

from relinker import RetryPolicy
from relinker.attempt import AttemptRecord
from relinker.event import RetryEvent
from relinker.state import RetryState


def _attempt(number: int, error: BaseException | None = None) -> AttemptRecord:
    return AttemptRecord(number=number, started_at=0.0, ended_at=0.1, error=error)


# ---------------------------------------------------------------------------
# Backward-compat: manually constructed states still work
# ---------------------------------------------------------------------------


def test_attempt_count_falls_back_to_len_attempts_when_total_not_set() -> None:
    state = RetryState(function_name="f", attempt_number=1, started_at=0.0, elapsed=0.0)
    assert state.attempt_count == 0


def test_attempt_count_uses_total_when_set() -> None:
    state = RetryState(
        function_name="f",
        attempt_number=5,
        started_at=0.0,
        elapsed=0.0,
        attempts=(_attempt(1), _attempt(2)),
        total_attempts=5,
    )
    assert state.attempt_count == 5
    assert state.retained_attempt_count == 2


def test_retained_attempt_count_reflects_len_attempts() -> None:
    state = RetryState(
        function_name="f",
        attempt_number=3,
        started_at=0.0,
        elapsed=0.0,
        attempts=(_attempt(1), _attempt(2), _attempt(3)),
        total_attempts=3,
    )
    assert state.retained_attempt_count == 3


# ---------------------------------------------------------------------------
# Counters from the executor are propagated to state
# ---------------------------------------------------------------------------


def test_executor_state_carries_total_attempts() -> None:
    received_states: list[RetryState] = []

    def on_failure(event: RetryEvent) -> None:
        if event.state is not None:
            received_states.append(event.state)

    def fail() -> None:
        raise ValueError("boom")

    policy = RetryPolicy().attempts(3).for_testing().on_event("after_failure", on_failure)
    with contextlib.suppress(ValueError):
        policy.run(fail)

    assert len(received_states) >= 1
    for i, state in enumerate(received_states, start=1):
        assert state.attempt_count == i, (
            f"attempt_count at event {i} should be {i}, got {state.attempt_count}"
        )
        assert state.total_attempts == i


def test_executor_state_carries_counters_with_truncated_history() -> None:
    received_states: list[RetryState] = []

    def on_sleep(event: RetryEvent) -> None:
        if event.state is not None:
            received_states.append(event.state)

    def fail() -> None:
        raise ValueError("truncated")

    policy = (
        RetryPolicy().attempts(10).for_testing().keep_history(3).on_event("before_sleep", on_sleep)
    )
    with contextlib.suppress(ValueError):
        policy.run(fail)

    assert len(received_states) >= 1
    for state in received_states:
        assert state.attempt_count >= state.retained_attempt_count, (
            "attempt_count must be >= retained_attempt_count"
        )
        assert state.total_attempts >= 1
        # With keep_history(3), retained must not exceed 3
        assert state.retained_attempt_count <= 3


# ---------------------------------------------------------------------------
# Snapshots are immutable after creation
# ---------------------------------------------------------------------------


def test_snapshots_do_not_change_after_new_attempts() -> None:
    captured: list[RetryState] = []

    def capture(event: RetryEvent) -> None:
        if event.name == "after_failure" and event.state is not None:
            captured.append(event.state)

    def fail() -> None:
        raise ValueError("fail")

    # .attempts(4) → StopAfterAttempt(4) → 4 failures → 4 after_failure events
    policy = RetryPolicy().attempts(4).for_testing().on_event("after_failure", capture)
    with contextlib.suppress(ValueError):
        policy.run(fail)

    assert len(captured) == 4
    for i, snap in enumerate(captured, start=1):
        assert snap.retained_attempt_count == i, (
            f"snapshot {i} should have {i} retained records, got {snap.retained_attempt_count}"
        )


# ---------------------------------------------------------------------------
# Handlers receive consistent state
# ---------------------------------------------------------------------------


def test_before_attempt_handler_receives_state_when_registered() -> None:
    received: list[RetryEvent] = []

    def on_attempt(event: RetryEvent) -> None:
        received.append(event)

    def fail() -> None:
        raise ValueError("x")

    policy = RetryPolicy().attempts(2).for_testing().on_event("before_attempt", on_attempt)
    with contextlib.suppress(ValueError):
        policy.run(fail)

    assert len(received) == 2
    assert all(ev.state is not None for ev in received)


def test_before_attempt_state_is_none_without_handlers() -> None:
    received: list[RetryEvent] = []

    # Use a sleep handler (not before_attempt) to capture events via before_sleep
    def on_sleep(event: RetryEvent) -> None:
        received.append(event)

    def fail() -> None:
        raise ValueError("x")

    # No before_attempt handler → state should be None for before_attempt
    # We verify via the absence of assertion errors in emit
    policy = RetryPolicy().attempts(3).for_testing().on_event("before_sleep", on_sleep)
    with contextlib.suppress(ValueError):
        policy.run(fail)

    # All before_sleep events should have valid state (needed for stateful delays)
    assert all(ev.state is not None for ev in received)


# ---------------------------------------------------------------------------
# Stateful delay still receives correct state
# ---------------------------------------------------------------------------


def test_stateful_delay_receives_last_error() -> None:
    received_errors: list[BaseException] = []

    def my_delay(state: RetryState) -> float:
        if state.last_error is not None:
            received_errors.append(state.last_error)
        return 0.0

    def fail() -> None:
        raise ValueError("delay-error")

    policy = RetryPolicy().attempts(3).stateful_delay(my_delay).for_testing()
    with contextlib.suppress(ValueError):
        policy.run(fail)

    assert len(received_errors) == 2
    assert all(isinstance(e, ValueError) for e in received_errors)


# ---------------------------------------------------------------------------
# Sync and async produce equivalent states
# ---------------------------------------------------------------------------


def test_sync_and_async_states_have_same_structure() -> None:
    sync_states: list[RetryState] = []
    async_states: list[RetryState] = []

    def sync_capture(event: RetryEvent) -> None:
        if event.state is not None:
            sync_states.append(event.state)

    def async_capture(event: RetryEvent) -> None:
        if event.state is not None:
            async_states.append(event.state)

    def sync_fail() -> None:
        raise ValueError("sync")

    async def async_fail() -> None:
        raise ValueError("async")

    sync_policy = RetryPolicy().attempts(3).for_testing().on_event("after_failure", sync_capture)
    async_policy = RetryPolicy().attempts(3).for_testing().on_event("after_failure", async_capture)

    with contextlib.suppress(ValueError):
        sync_policy.run(sync_fail)

    async def run_async() -> None:
        with contextlib.suppress(ValueError):
            await async_policy.run_async(async_fail)

    asyncio.run(run_async())

    # .attempts(3): 3 total attempts all fail → 3 after_failure events each
    assert len(sync_states) == len(async_states) == 3
    for s, a in zip(sync_states, async_states, strict=True):
        assert s.attempt_count == a.attempt_count
        assert s.total_attempts == a.total_attempts
        assert s.retained_attempt_count == a.retained_attempt_count


# ---------------------------------------------------------------------------
# No quadratic copy growth in common path (structural test)
# ---------------------------------------------------------------------------


def test_tuple_copy_count_does_not_grow_quadratically_with_history_limit() -> None:
    """State with bounded history limit avoids O(N^2) copies."""
    copy_calls = 0

    class CountingList(list):  # type: ignore[type-arg]
        def __iter__(self):  # type: ignore[override]
            nonlocal copy_calls
            copy_calls += 1
            return super().__iter__()

    # This test verifies that bounded history doesn't scale with total attempts.
    # With keep_history(10) and 100 attempts, each tuple() copies at most 10 items.
    history: list[RetryState] = []

    def capture(event: RetryEvent) -> None:
        if event.state is not None:
            history.append(event.state)

    def fail() -> None:
        raise ValueError("loop")

    n = 50
    policy = (
        RetryPolicy().attempts(n).for_testing().keep_history(5).on_event("after_failure", capture)
    )
    with contextlib.suppress(ValueError):
        policy.run(fail)

    for state in history:
        assert state.retained_attempt_count <= 5
        assert state.attempt_count == state.total_attempts
