"""Regression contracts for max_time checks before retry sleep."""

from __future__ import annotations

from relinker.internal.exhaustion import should_stop_before_sleep
from relinker.stop.max_time import StopAfterDelay


def test_max_time_before_sleep_uses_reached_budget_boundary() -> None:
    strategy = StopAfterDelay(5.0)

    assert should_stop_before_sleep(strategy, 1, 4.0, 0.999999) is False
    assert should_stop_before_sleep(strategy, 1, 4.0, 1.0) is True
    assert should_stop_before_sleep(strategy, 1, 4.0, 1.000001) is True
