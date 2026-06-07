"""Regression contracts for unsupported async event handlers."""

from __future__ import annotations

import pytest

from relinker import InvalidRetryConfigError, RetryPolicy
from relinker.event import RetryEvent


async def async_handler(_: RetryEvent) -> None:
    pass


class AsyncHandler:
    async def __call__(self, _: RetryEvent) -> None:
        pass


def test_async_event_handler_function_is_rejected_at_registration() -> None:
    with pytest.raises(
        InvalidRetryConfigError,
        match="Async event handlers are not supported",
    ):
        RetryPolicy().on_event("before_attempt", async_handler)


def test_async_event_handler_callable_object_is_rejected_at_registration() -> None:
    with pytest.raises(
        InvalidRetryConfigError,
        match="Async event handlers are not supported",
    ):
        RetryPolicy().on_event("before_attempt", AsyncHandler())
