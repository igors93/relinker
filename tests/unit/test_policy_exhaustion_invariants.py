from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.result import RetryResult


def _fallback(result: RetryResult[object]) -> str:
    return "safe"


def _exception_factory(result: RetryResult[object]) -> BaseException:
    return ValueError("custom")


def test_default_exhaustion_configuration_is_valid() -> None:
    policy = RetryPolicy()

    assert policy.should_raise_last is True
    assert policy.should_return_result is False
    assert policy.exhausted_callback is None
    assert policy.exhausted_exception_factory is None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"should_raise_last": False, "should_return_result": True},
        {"should_raise_last": False, "exhausted_callback": _fallback},
        {"should_raise_last": False, "exhausted_exception_factory": _exception_factory},
    ],
)
def test_individual_exhaustion_configurations_are_valid(kwargs: dict[str, object]) -> None:
    RetryPolicy(**kwargs)


def test_raise_last_clears_previous_exhaustion_behavior() -> None:
    base = RetryPolicy().fallback_value("safe")
    derived = base.raise_last()

    assert base.exhausted_callback is not None
    assert base is not derived
    assert derived.should_raise_last is True
    assert derived.should_return_result is False
    assert derived.exhausted_callback is None
    assert derived.exhausted_exception_factory is None


@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy().fallback_value("safe").return_result(),
        RetryPolicy().on_exhausted_raise(ValueError("custom")).return_result(),
    ],
)
def test_return_result_clears_previous_exhaustion_behavior(policy: RetryPolicy[object]) -> None:
    assert policy.should_raise_last is False
    assert policy.should_return_result is True
    assert policy.exhausted_callback is None
    assert policy.exhausted_exception_factory is None


@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy().return_result().fallback_value("safe"),
        RetryPolicy().on_exhausted_raise(ValueError("custom")).fallback_value("safe"),
    ],
)
def test_fallback_clears_previous_exhaustion_behavior(policy: RetryPolicy[object]) -> None:
    assert policy.should_raise_last is False
    assert policy.should_return_result is False
    assert policy.exhausted_callback is not None
    assert policy.exhausted_exception_factory is None


@pytest.mark.parametrize(
    "policy",
    [
        RetryPolicy().return_result().on_exhausted_raise(ValueError("custom")),
        RetryPolicy().fallback_value("safe").on_exhausted_raise(ValueError("custom")),
    ],
)
def test_custom_exception_clears_previous_exhaustion_behavior(
    policy: RetryPolicy[object],
) -> None:
    assert policy.should_raise_last is False
    assert policy.should_return_result is False
    assert policy.exhausted_callback is None
    assert policy.exhausted_exception_factory is not None


@pytest.mark.parametrize(
    "kwargs",
    [
        {"should_raise_last": True, "should_return_result": True},
        {"should_raise_last": True, "exhausted_callback": _fallback},
        {"should_raise_last": True, "exhausted_exception_factory": _exception_factory},
        {
            "should_raise_last": False,
            "should_return_result": True,
            "exhausted_callback": _fallback,
        },
        {
            "should_raise_last": False,
            "should_return_result": True,
            "exhausted_exception_factory": _exception_factory,
        },
        {
            "should_raise_last": False,
            "exhausted_callback": _fallback,
            "exhausted_exception_factory": _exception_factory,
        },
    ],
)
def test_contradictory_direct_exhaustion_configuration_is_rejected(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(
        InvalidRetryConfigError,
        match="exhaustion behaviors are mutually exclusive",
    ):
        RetryPolicy(**kwargs)
