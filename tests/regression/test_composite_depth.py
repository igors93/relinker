"""Regression contracts for deeply composed policies."""

from __future__ import annotations

from relinker import RetryPolicy
from relinker.delays.composite import AdditiveDelay
from relinker.delays.custom import CustomDelay
from relinker.delays.fixed import FixedDelay


def test_large_or_on_chain_decides_and_serializes_without_recursion_error() -> None:
    policy = RetryPolicy().on(ValueError)
    for _ in range(1200):
        policy = policy.or_on(KeyError)

    assert policy.condition.should_retry_exception(KeyError("retry"))
    assert not policy.condition.should_retry_exception(RuntimeError("no retry"))

    data = policy.to_dict()
    assert data["condition"]["type"] == "any"


def test_add_delay_preserves_nested_additive_arithmetic_order() -> None:
    nested = AdditiveDelay(
        (
            FixedDelay(1e16),
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
        .fixed_delay(1e16)
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
    nested = AdditiveDelay(
        (
            FixedDelay(1.0),
            AdditiveDelay(
                (
                    FixedDelay(1.0),
                    FixedDelay(1e16),
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
                    FixedDelay(1e16),
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
    policy = RetryPolicy().fixed_delay(0.0)
    for _ in range(1200):
        policy = policy.add_delay(FixedDelay(0.0))

    assert policy.delay_strategy.next_delay(1) == 0.0


def test_jitter_keeps_delay_inside_base_plus_jitter_interval() -> None:
    policy = RetryPolicy().fixed_delay(5.0).jitter(minimum=1.0, maximum=2.0, seed=1)

    delay = policy.delay_strategy.next_delay(3)

    assert 6.0 <= delay <= 7.0
