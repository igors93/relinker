"""Contracts for exception matching, control flow, and callable kinds."""

from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy, TryAgain

from ._support import policy_without_sleep


class ParentFailure(Exception):
    pass


class ChildFailure(ParentFailure):
    pass


class SiblingFailure(Exception):
    pass


def test_exception_subclass_matches_configured_parent_type() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ChildFailure("temporary")
        return "ok"

    policy = policy_without_sleep(RetryPolicy().attempts(2).on(ParentFailure))
    assert policy.run(operation) == "ok"
    assert calls == 2


def test_configured_child_type_does_not_match_parent_instance() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise ParentFailure("not a child")

    policy = policy_without_sleep(RetryPolicy().attempts(3).on(ChildFailure))
    with pytest.raises(ParentFailure, match="not a child"):
        policy.run(operation)
    assert calls == 1


def test_sibling_exception_is_not_retried() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise SiblingFailure("permanent")

    policy = policy_without_sleep(RetryPolicy().attempts(3).on(ParentFailure))
    with pytest.raises(SiblingFailure, match="permanent"):
        policy.run(operation)
    assert calls == 1


def test_multiple_configured_exception_types_are_independently_matched() -> None:
    errors = iter([TimeoutError("one"), ConnectionError("two")])
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls <= 2:
            raise next(errors)
        return "ok"

    policy = policy_without_sleep(RetryPolicy().attempts(3).on(TimeoutError, ConnectionError))
    assert policy.run(operation) == "ok"
    assert calls == 3


def test_try_again_respects_attempt_limit() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise TryAgain("not ready")

    result = (
        policy_without_sleep(RetryPolicy().attempts(3).on(ValueError))
        .return_result()
        .run(operation)
    )
    assert result.exhausted is True
    assert result.attempt_count == 3
    assert calls == 3


def test_try_again_can_recover_on_a_later_attempt() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TryAgain("pending")
        return "ready"

    policy = policy_without_sleep(RetryPolicy().attempts(3).on(KeyError))
    assert policy.run(operation) == "ready"
    assert calls == 3


def test_keyboard_interrupt_is_never_converted_to_retry_result() -> None:
    policy = RetryPolicy().attempts(3).return_result()

    with pytest.raises(KeyboardInterrupt):
        policy.run(lambda: (_ for _ in ()).throw(KeyboardInterrupt()))


@pytest.mark.asyncio
async def test_async_cancelled_error_is_never_swallowed() -> None:
    async def operation() -> None:
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await RetryPolicy().attempts(3).return_result().run_async(operation)


def test_run_rejects_coroutine_function_before_calling_it() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    with pytest.raises(InvalidRetryConfigError, match=r"run\(\)"):
        RetryPolicy().run(operation)  # type: ignore[arg-type]
    assert calls == 0


@pytest.mark.asyncio
async def test_run_async_rejects_non_awaitable_result_without_retrying() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        return "not awaitable"

    with pytest.raises(InvalidRetryConfigError, match="awaitable"):
        policy = policy_without_sleep(RetryPolicy().attempts(3))
        await policy.run_async(operation)  # type: ignore[arg-type]
    assert calls == 1


def test_generator_function_is_rejected_before_iteration() -> None:
    def operation() -> Any:
        yield "value"

    with pytest.raises(InvalidRetryConfigError, match="Generator"):
        RetryPolicy().run(operation)


@pytest.mark.asyncio
async def test_async_generator_function_is_rejected_before_iteration() -> None:
    async def operation() -> Any:
        yield "value"

    with pytest.raises(InvalidRetryConfigError, match="Async generator"):
        await RetryPolicy().run_async(operation)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_sync_factory_returning_coroutine_is_supported_by_run_async() -> None:
    calls = 0

    async def result() -> str:
        return "ok"

    def factory() -> Any:
        nonlocal calls
        calls += 1
        return result()

    assert await RetryPolicy().run_async(factory) == "ok"  # type: ignore[arg-type]
    assert calls == 1


@pytest.mark.asyncio
async def test_partial_wrapped_async_function_remains_async_retryable() -> None:
    calls = 0

    async def operation(prefix: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError("temporary")
        return prefix + "ok"

    wrapped = partial(operation, "prefix-")
    policy = policy_without_sleep(RetryPolicy().attempts(2).on(TimeoutError))
    assert await policy.run_async(wrapped) == "prefix-ok"
    assert calls == 2
