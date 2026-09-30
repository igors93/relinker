"""Regression tests: parametrized generics can be instantiated on every Python.

``RetryPolicy[str]()`` and ``RetryResult[str](...)`` raised
``TypeError: super(type, obj): obj must be an instance or subtype of type`` on
Python 3.10. ``typing`` assigns ``__orig_class__`` after construction, and the
``__setattr__`` generated for a frozen dataclass with ``slots=True`` called
``super()`` with the pre-slots class. The type-checking examples in
tests/typing use this spelling but are never executed, so nothing caught it.
"""

from __future__ import annotations

import dataclasses

import pytest

from relinker import RetryPolicy, RetryResult


def test_parametrized_policy_can_be_instantiated_and_run() -> None:
    policy = RetryPolicy[str]().attempts(2).on(TimeoutError).no_delay()

    assert policy.run(lambda: "ok") == "ok"


def test_parametrized_result_can_be_instantiated() -> None:
    result = RetryResult[str](attempts=(), value="ok")

    assert result.value == "ok"
    assert result.succeeded


@pytest.mark.parametrize(
    "instance",
    [RetryPolicy[str](), RetryResult[str](attempts=())],
    ids=["policy", "result"],
)
def test_parametrized_instances_remain_immutable(instance: object) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.name = "changed"  # type: ignore[attr-defined]
