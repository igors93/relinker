"""Regression contracts for deeply composed policies."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy, RetryState
from relinker.delays.composite import AdditiveDelay
from relinker.delays.custom import CustomDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.random_delay import RandomDelay
from relinker.delays.stateful import StatefulCustomDelay


def _deep_additive_policy() -> RetryPolicy[object]:
    policy = RetryPolicy().fixed_delay(0.0)
    for _ in range(1200):
        policy = policy.add_delay(FixedDelay(0.0))
    return policy


def _left_additive_depth(delay_data: object) -> int:
    depth = 0
    current = delay_data
    while isinstance(current, dict) and current.get("type") == "additive":
        strategies = current["strategies"]
        assert isinstance(strategies, list)
        assert len(strategies) == 2
        depth += 1
        current = strategies[0]
    return depth


def _contains_delay_type(delay_data: object, expected_type: str) -> bool:
    stack = [delay_data]
    while stack:
        current = stack.pop()
        if not isinstance(current, dict):
            continue
        if current.get("type") == expected_type:
            return True
        strategies = current.get("strategies")
        if isinstance(strategies, list):
            stack.extend(strategies)
    return False


def test_large_or_on_chain_decides_and_serializes_without_recursion_error() -> None:
    policy = RetryPolicy().on(ValueError)
    for _ in range(1200):
        policy = policy.or_on(KeyError)

    assert policy.condition.should_retry_exception(KeyError("retry"))
    assert not policy.condition.should_retry_exception(RuntimeError("no retry"))

    data = policy.to_dict()
    assert data["condition"]["type"] == "any"


def test_add_delay_preserves_nested_additive_arithmetic_order() -> None:
    # Use a large but valid value to test ordering: the dominant term must come
    # first so floating-point arithmetic is the same in both forms.
    large = 80_000.0
    nested = AdditiveDelay(
        (
            FixedDelay(large),
            AdditiveDelay(
                (
                    FixedDelay(1.0),
                    FixedDelay(1.0),
                )
            ),
        )
    )

    policy = (
        RetryPolicy()
        .fixed_delay(large)
        .add_delay(
            AdditiveDelay(
                (
                    FixedDelay(1.0),
                    FixedDelay(1.0),
                )
            )
        )
    )

    assert policy.delay_strategy.next_delay(1) == nested.next_delay(1)


def test_add_delay_preserves_observable_nested_additive_arithmetic_order() -> None:
    large = 80_000.0
    nested = AdditiveDelay(
        (
            FixedDelay(1.0),
            AdditiveDelay(
                (
                    FixedDelay(1.0),
                    FixedDelay(large),
                )
            ),
        )
    )

    policy = (
        RetryPolicy()
        .fixed_delay(1.0)
        .add_delay(
            AdditiveDelay(
                (
                    FixedDelay(1.0),
                    FixedDelay(large),
                )
            )
        )
    )

    assert policy.delay_strategy.next_delay(1) == nested.next_delay(1)


def test_add_delay_keeps_normal_additive_delay_value() -> None:
    policy = RetryPolicy().fixed_delay(1.5).add_delay(FixedDelay(2.5))

    assert policy.delay_strategy.next_delay(1) == 4.0


def test_additive_delay_preserves_callback_order_without_duplicate_calls() -> None:
    calls: list[str] = []

    def callback(label: str, value: float):
        def delay(_: int) -> float:
            calls.append(label)
            return value

        return delay

    delay = AdditiveDelay(
        (
            CustomDelay(callback("left", 1.0)),
            AdditiveDelay(
                (
                    CustomDelay(callback("middle", 2.0)),
                    CustomDelay(callback("right", 3.0)),
                )
            ),
        )
    )

    assert delay.next_delay(1) == 6.0
    assert calls == ["left", "middle", "right"]


def test_deep_add_delay_chain_resolves_without_recursion_error() -> None:
    policy = _deep_additive_policy()

    assert policy.delay_strategy.next_delay(1) == 0.0


def test_deep_add_delay_chain_to_dict_preserves_structure_without_recursion_error() -> None:
    data = _deep_additive_policy().to_dict()

    assert _left_additive_depth(data["delay"]) == 1200


def test_deep_add_delay_chain_simulate_without_recursion_error() -> None:
    simulation = _deep_additive_policy().simulate(attempts=2)

    assert simulation.attempt_count == 2


def test_deep_add_delay_chain_preview_without_recursion_error() -> None:
    preview = _deep_additive_policy().preview(attempts=2)

    assert "Attempts previewed: 2" in preview


def test_deep_add_delay_chain_timeline_without_recursion_error() -> None:
    timeline = _deep_additive_policy().timeline(attempts=2)

    assert "Attempts simulated: 2" in timeline


def test_deep_add_delay_chain_warnings_without_recursion_error() -> None:
    warnings = _deep_additive_policy().warnings()

    assert "no_delay" in {warning.code for warning in warnings}


def test_deep_add_delay_chain_doctor_without_recursion_error() -> None:
    report = _deep_additive_policy().doctor()

    assert "no_delay" in {warning.code for warning in report.warnings}


def test_deep_mixed_additive_delay_inspection_preserves_contracts() -> None:
    callback_calls: list[str] = []

    def custom_delay(_: int) -> float:
        callback_calls.append("custom")
        return 0.0

    def stateful_delay(_: RetryState) -> float:
        callback_calls.append("stateful")
        return 0.0

    policy = (
        RetryPolicy()
        .attempts(12)
        .fixed_delay(1.0)
        .add_delay(RandomDelay(minimum=0.1, maximum=0.2, seed=1))
        .add_delay(CustomDelay(custom_delay))
        .add_delay(StatefulCustomDelay(stateful_delay))
    )
    for _ in range(1200):
        policy = policy.add_delay(FixedDelay(0.0))

    data = policy.to_dict()
    delay_data = data["delay"]

    assert _left_additive_depth(delay_data) == 1203
    assert _contains_delay_type(delay_data, "fixed")
    assert _contains_delay_type(delay_data, "random")
    assert _contains_delay_type(delay_data, "custom")
    assert _contains_delay_type(delay_data, "stateful_custom")
    assert callback_calls == []

    with pytest.raises(
        InvalidRetryConfigError,
        match="custom delay callbacks",
    ):
        policy.simulate(attempts=2)
    assert callback_calls == []

    with pytest.raises(
        InvalidRetryConfigError,
        match="custom delay callbacks",
    ):
        policy.preview(attempts=2)
    assert callback_calls == []

    warning_codes = {warning.code for warning in policy.warnings()}
    doctor_codes = {warning.code for warning in policy.doctor().warnings}

    assert "no_delay" not in warning_codes
    assert "missing_jitter" not in warning_codes
    assert "no_delay" not in doctor_codes
    assert "missing_jitter" not in doctor_codes
    assert callback_calls == []


def test_jitter_keeps_delay_inside_base_plus_jitter_interval() -> None:
    policy = RetryPolicy().fixed_delay(5.0).jitter(minimum=1.0, maximum=2.0, seed=1)

    delay = policy.delay_strategy.next_delay(3)

    assert 6.0 <= delay <= 7.0
