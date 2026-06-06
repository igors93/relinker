"""Shared deterministic helpers for behavioral contract tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from relinker import RetryPolicy
from relinker.event import EventName, RetryEvent

ALL_EVENT_NAMES: tuple[EventName, ...] = (
    "before_attempt",
    "after_success",
    "after_failure",
    "before_sleep",
    "after_giveup",
)


def no_sleep(_: float) -> None:
    """Do not block during synchronous contract tests."""


async def async_no_sleep(_: float) -> None:
    """Do not block during asynchronous contract tests."""


@dataclass
class FakeClock:
    """Small monotonic clock used to make wait contracts deterministic."""

    value: float = 0.0

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.value += seconds

    async def async_sleep(self, seconds: float) -> None:
        self.value += seconds


def policy_without_sleep(policy: RetryPolicy[Any]) -> RetryPolicy[Any]:
    """Return ``policy`` with deterministic no-op sync and async sleeps."""

    return policy.with_sleep(no_sleep, async_no_sleep)


def collect_all_events(
    policy: RetryPolicy[Any],
    events: list[RetryEvent],
) -> RetryPolicy[Any]:
    """Attach one collector to every public retry event."""

    configured = policy
    for name in ALL_EVENT_NAMES:
        configured = configured.on_event(name, events.append)
    return configured


def patch_sync_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Patch all synchronous runtime clock readers used by retry execution."""

    monkeypatch.setattr("relinker.executors.sync.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)


def patch_async_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Patch all asynchronous runtime clock readers used by retry execution."""

    monkeypatch.setattr("relinker.executors.async_.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)


def patch_context_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Patch all context-manager clock readers used by retry execution."""

    monkeypatch.setattr("relinker.context.now", clock.now)
    monkeypatch.setattr("relinker.internal.executor_helpers.now", clock.now)
    monkeypatch.setattr("relinker.internal.retry_wait.now", clock.now)
