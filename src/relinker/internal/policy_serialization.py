"""Structured, read-only policy representation for RetryPolicy.to_dict()."""

from __future__ import annotations

from typing import Any, cast

from relinker.conditions.composite import AllCondition, AnyCondition
from relinker.conditions.custom import CustomCondition
from relinker.conditions.exception import ExceptionCondition
from relinker.conditions.result import ResultCondition
from relinker.delays.chain import ChainDelay
from relinker.delays.composite import AdditiveDelay
from relinker.delays.custom import CustomDelay
from relinker.delays.exponential import ExponentialDelay
from relinker.delays.fixed import FixedDelay
from relinker.delays.linear import LinearDelay
from relinker.delays.random_delay import RandomDelay
from relinker.delays.random_exponential import RandomExponentialDelay
from relinker.delays.stateful import StatefulCustomDelay
from relinker.event import EventHandlerRegistration
from relinker.stop.attempts import StopAfterAttempt
from relinker.stop.composite import AllStopStrategy, AnyStopStrategy
from relinker.stop.forever import StopForever
from relinker.stop.max_time import StopAfterDelay


def _callable_name(callback: object) -> str:
    name = getattr(callback, "__name__", None)
    if name in {None, "<lambda>"}:
        return "<anonymous>"
    module = getattr(callback, "__module__", None)
    qualname = getattr(callback, "__qualname__", name)
    if module:
        return f"{module}.{qualname}"
    return str(qualname)


def _event_handler_to_dict(registration: object) -> dict[str, str]:
    if isinstance(registration, EventHandlerRegistration):
        return {
            "event": registration.name,
            "callable": _callable_name(registration.handler),
            "failure_mode": registration.failure_mode,
        }

    name, handler = cast(tuple[str, object], registration)
    return {
        "event": name,
        "callable": _callable_name(handler),
        "failure_mode": "propagate",
    }


def _exception_name(exception_type: type[BaseException]) -> str:
    return f"{exception_type.__module__}.{exception_type.__qualname__}"


def _stop_to_dict(strategy: object) -> dict[str, Any]:
    if isinstance(strategy, StopAfterAttempt):
        return {"type": "attempts", "maximum": strategy.maximum}
    if isinstance(strategy, StopAfterDelay):
        return {"type": "max_time", "seconds": strategy.seconds}
    if isinstance(strategy, StopForever):
        return {"type": "forever"}
    if isinstance(strategy, AnyStopStrategy):
        return {"type": "any", "strategies": [_stop_to_dict(item) for item in strategy.strategies]}
    if isinstance(strategy, AllStopStrategy):
        return {"type": "all", "strategies": [_stop_to_dict(item) for item in strategy.strategies]}
    return {"type": "custom", "class": strategy.__class__.__name__}


def _condition_to_dict(condition: object) -> dict[str, Any]:
    if isinstance(condition, ExceptionCondition):
        return {
            "type": "exceptions",
            "exceptions": [_exception_name(item) for item in condition.exception_types],
        }
    if isinstance(condition, ResultCondition):
        return {"type": "result", "predicate": _callable_name(condition.predicate)}
    if isinstance(condition, CustomCondition):
        return {"type": "custom", "callable": _callable_name(condition.callback)}
    if isinstance(condition, AnyCondition):
        return {
            "type": "any",
            "conditions": [_condition_to_dict(item) for item in condition.conditions],
        }
    if isinstance(condition, AllCondition):
        return {
            "type": "all",
            "conditions": [_condition_to_dict(item) for item in condition.conditions],
        }
    return {"type": "custom", "class": condition.__class__.__name__}


def _delay_to_shallow_dict(strategy: object) -> dict[str, Any]:
    if isinstance(strategy, FixedDelay):
        return {"type": "fixed", "seconds": strategy.seconds}
    if isinstance(strategy, LinearDelay):
        return {
            "type": "linear",
            "start": strategy.start,
            "step": strategy.step,
            "maximum": strategy.maximum,
        }
    if isinstance(strategy, ExponentialDelay):
        return {
            "type": "exponential",
            "base": strategy.base,
            "factor": strategy.factor,
            "maximum": strategy.maximum,
        }
    if isinstance(strategy, RandomDelay):
        return {
            "type": "random",
            "minimum": strategy.minimum,
            "maximum": strategy.maximum,
            "seed": strategy.seed,
        }
    if isinstance(strategy, RandomExponentialDelay):
        return {
            "type": "random_exponential",
            "base": strategy.base,
            "factor": strategy.factor,
            "minimum": strategy.minimum,
            "maximum": strategy.maximum,
            "seed": strategy.seed,
        }
    if isinstance(strategy, ChainDelay):
        return {"type": "chain", "delays": list(strategy.delays)}
    if isinstance(strategy, AdditiveDelay):
        return {"type": "additive", "strategies": []}
    if isinstance(strategy, CustomDelay):
        return {"type": "custom", "callable": _callable_name(strategy.callback)}
    if isinstance(strategy, StatefulCustomDelay):
        return {"type": "stateful_custom", "callable": _callable_name(strategy.callback)}
    return {"type": "custom", "class": strategy.__class__.__name__}


def _delay_to_dict(strategy: object) -> dict[str, Any]:
    root = _delay_to_shallow_dict(strategy)
    if not isinstance(strategy, AdditiveDelay):
        return root

    stack: list[tuple[AdditiveDelay, dict[str, Any]]] = [(strategy, root)]
    while stack:
        current, current_data = stack.pop()
        child_data_list = cast(list[dict[str, Any]], current_data["strategies"])
        for child in current.strategies:
            child_data = _delay_to_shallow_dict(child)
            child_data_list.append(child_data)
            if isinstance(child, AdditiveDelay):
                stack.append((child, child_data))
    return root


def _exception_exhaustion_to_dict(policy: Any) -> dict[str, Any]:
    if policy.should_return_result:
        return {"type": "return_result"}
    if policy.exhausted_callback is not None:
        return {"type": "fallback", "callable": _callable_name(policy.exhausted_callback)}
    if policy.exhausted_exception_factory is not None:
        return {
            "type": "raise_custom",
            "callable": _callable_name(policy.exhausted_exception_factory),
        }
    if policy.should_raise_last:
        return {"type": "raise_last"}
    return {"type": "return_none"}


def _result_exhaustion_to_dict(policy: Any) -> dict[str, Any]:
    if policy.should_return_result:
        return {"type": "return_result"}
    if policy.exhausted_callback is not None:
        return {"type": "fallback", "callable": _callable_name(policy.exhausted_callback)}
    if policy.exhausted_exception_factory is not None:
        return {
            "type": "raise_custom",
            "callable": _callable_name(policy.exhausted_exception_factory),
        }
    if policy.result_exhausted_behavior == "raise":
        return {"type": "raise"}
    return {"type": "return_last"}


def _exhaustion_to_dict(policy: Any) -> dict[str, Any]:
    return {
        "exception": _exception_exhaustion_to_dict(policy),
        "result": _result_exhaustion_to_dict(policy),
    }


def policy_to_dict(policy: Any) -> dict[str, Any]:
    """Return a structured representation of policy configuration only."""
    budget = policy.retry_budget
    retry_budget: dict[str, Any]
    if budget is None:
        retry_budget = {"enabled": False}
    else:
        retry_budget = {
            "enabled": True,
            "key": policy.retry_budget_key,
            "max_retries": budget.max_retries,
            "per": budget.per,
        }

    return {
        "name": policy.name,
        "stop": _stop_to_dict(policy.stop_strategy),
        "condition": _condition_to_dict(policy.condition),
        "delay": _delay_to_dict(policy.delay_strategy),
        "exhaustion": _exhaustion_to_dict(policy),
        "history_limit": policy.history_limit,
        "retry_budget": retry_budget,
        "testing": {"no_real_sleep": bool(getattr(policy, "testing_mode", False))},
        "callbacks": {
            "event_handlers": [
                _event_handler_to_dict(registration) for registration in policy.event_handlers
            ]
        },
    }
