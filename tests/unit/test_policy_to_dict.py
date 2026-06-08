from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from relinker import RetryBudget, RetryPolicy
from relinker.delays import FixedDelay
from relinker.result_conditions import retry_if_none


def custom_condition(error: BaseException | None, value: object) -> bool:
    return error is not None or value is None


def custom_delay(attempt_number: int) -> float:
    return float(attempt_number)


def _assert_simple_types(value: object) -> None:
    if value is None or isinstance(value, bool | int | float | str):
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            assert isinstance(key, str)
            _assert_simple_types(item)
        return
    if isinstance(value, Sequence) and not isinstance(value, str):
        for item in value:
            _assert_simple_types(item)
        return
    raise AssertionError(f"non-simple value in to_dict(): {value!r}")


def test_to_dict_for_default_policy() -> None:
    data = RetryPolicy().to_dict()

    assert data["name"] is None
    assert data["stop"] == {"type": "attempts", "maximum": 3}
    assert data["condition"]["type"] == "exceptions"
    assert data["delay"] == {"type": "fixed", "seconds": 0}
    assert data["exhaustion"] == {
        "exception": {"type": "raise_last"},
        "result": {"type": "return_last"},
    }
    assert data["history_limit"] == 1000
    assert data["retry_budget"] == {"enabled": False}
    assert data["testing"] == {"no_real_sleep": False}


def test_to_dict_for_named_budgeted_policy() -> None:
    budget = RetryBudget(max_retries=20, per=60)
    policy = (
        RetryPolicy()
        .named("payments-api")
        .attempts(5)
        .on(TimeoutError)
        .exponential_delay(base=1, factor=2, maximum=30)
        .with_retry_budget(budget, key="payments-api")
    )

    data = policy.to_dict()

    assert data["name"] == "payments-api"
    assert data["stop"] == {"type": "attempts", "maximum": 5}
    assert data["condition"] == {
        "type": "exceptions",
        "exceptions": ["builtins.TimeoutError"],
    }
    assert data["delay"] == {
        "type": "exponential",
        "base": 1,
        "factor": 2,
        "maximum": 30,
    }
    assert data["retry_budget"] == {
        "enabled": True,
        "key": "payments-api",
        "max_retries": 20,
        "per": 60.0,
    }


def test_to_dict_represents_stop_variants_and_composites() -> None:
    assert RetryPolicy().max_time(5).to_dict()["stop"] == {"type": "max_time", "seconds": 5}
    assert RetryPolicy().forever().to_dict()["stop"] == {"type": "forever"}

    data = RetryPolicy().attempts(5).or_stop_after_time(10).to_dict()

    assert data["stop"] == {
        "type": "any",
        "strategies": [
            {"type": "attempts", "maximum": 5},
            {"type": "max_time", "seconds": 10},
        ],
    }


def test_to_dict_represents_condition_variants() -> None:
    result_condition = RetryPolicy().retry_if_result(retry_if_none()).to_dict()["condition"]
    custom = RetryPolicy().retry_if(custom_condition).to_dict()["condition"]
    composite = (
        RetryPolicy().on(TimeoutError).or_retry_if_result(retry_if_none()).to_dict()["condition"]
    )

    assert result_condition["type"] == "result"
    assert result_condition["predicate"].endswith("retry_if_none.<locals>.predicate")
    assert custom["type"] == "custom"
    assert custom["callable"].endswith("test_policy_to_dict.custom_condition")
    assert composite["type"] == "any"


def test_to_dict_represents_delay_variants() -> None:
    assert RetryPolicy().linear_delay(start=1, step=2, maximum=5).to_dict()["delay"] == {
        "type": "linear",
        "start": 1,
        "step": 2,
        "maximum": 5,
    }
    assert RetryPolicy().chain_delay([1, 2]).to_dict()["delay"] == {
        "type": "chain",
        "delays": [1, 2],
    }
    assert RetryPolicy().random_delay(minimum=1, maximum=3, seed=7).to_dict()["delay"] == {
        "type": "random",
        "minimum": 1,
        "maximum": 3,
        "seed": 7,
    }
    assert RetryPolicy().random_exponential_delay(seed=7).to_dict()["delay"]["type"] == (
        "random_exponential"
    )
    assert (
        RetryPolicy().fixed_delay(1).jitter(maximum=0.5, seed=1).to_dict()["delay"]["type"]
        == "additive"
    )
    custom_delay_data = RetryPolicy().custom_delay(custom_delay).to_dict()["delay"]
    assert custom_delay_data["type"] == "custom"
    assert custom_delay_data["callable"].endswith("test_policy_to_dict.custom_delay")


def test_to_dict_represents_callbacks_fallback_and_testing() -> None:
    def fallback(result: Any) -> str:
        return "cached"

    policy = (
        RetryPolicy()
        .attempts(2)
        .on(TimeoutError)
        .fallback(fallback)
        .on_giveup(lambda event: None)
        .for_testing()
    )
    data = policy.to_dict()

    assert data["exhaustion"]["exception"]["type"] == "fallback"
    assert data["exhaustion"]["result"]["type"] == "fallback"
    assert data["exhaustion"]["exception"]["callable"].endswith(
        "test_policy_to_dict.test_to_dict_represents_callbacks_fallback_and_testing.<locals>.fallback"
    )
    assert data["exhaustion"]["exception"] == data["exhaustion"]["result"]
    assert data["callbacks"]["event_handlers"] == [
        {"event": "after_giveup", "callable": "<anonymous>", "failure_mode": "propagate"}
    ]
    assert data["testing"] == {"no_real_sleep": True}


def test_to_dict_represents_event_handler_failure_mode() -> None:
    data = (
        RetryPolicy().on_event("before_sleep", lambda event: None, failure_mode="isolate").to_dict()
    )

    assert data["callbacks"]["event_handlers"] == [
        {"event": "before_sleep", "callable": "<anonymous>", "failure_mode": "isolate"}
    ]


def test_to_dict_represents_result_exhaustion_options() -> None:
    assert RetryPolicy().retry_if_result(retry_if_none()).raise_on_result_exhausted().to_dict()[
        "exhaustion"
    ]["result"] == {"type": "raise"}
    assert RetryPolicy().retry_if_result(
        retry_if_none()
    ).return_last_on_result_exhausted().to_dict()["exhaustion"]["result"] == {"type": "return_last"}


def test_to_dict_represents_return_result_for_both_exhaustion_paths() -> None:
    data = RetryPolicy().return_result().to_dict()

    assert data["exhaustion"] == {
        "exception": {"type": "return_result"},
        "result": {"type": "return_result"},
    }


def test_to_dict_represents_custom_exhaustion_exception_for_both_paths() -> None:
    def factory(result: object) -> RuntimeError:
        return RuntimeError("exhausted")

    data = RetryPolicy().on_exhausted_raise(factory).to_dict()

    assert data["exhaustion"]["exception"]["type"] == "raise_custom"
    assert data["exhaustion"]["result"]["type"] == "raise_custom"
    assert data["exhaustion"]["exception"] == data["exhaustion"]["result"]
    assert data["exhaustion"]["exception"]["callable"].endswith(
        "test_policy_to_dict.test_to_dict_represents_custom_exhaustion_exception_for_both_paths.<locals>.factory"
    )


def test_to_dict_represents_unlimited_history() -> None:
    assert RetryPolicy().keep_history(None).to_dict()["history_limit"] is None


def test_to_dict_contains_only_simple_types_and_no_memory_addresses() -> None:
    data = RetryPolicy().custom_delay(lambda attempt: 0).to_dict()

    _assert_simple_types(data)
    assert "0x" not in repr(data)


def test_to_dict_returns_independent_deterministic_data() -> None:
    policy = RetryPolicy().attempts(3).add_delay(FixedDelay(1))

    first = policy.to_dict()
    second = policy.to_dict()
    first["stop"] = {"type": "changed"}

    assert second == policy.to_dict()
    assert second["stop"] == {"type": "attempts", "maximum": 3}
