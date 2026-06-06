from __future__ import annotations

import pytest

import relinker
import relinker.context as context
from relinker import RetryPolicy
from relinker.context import (
    AsyncRetryAttemptContext,
    AsyncRetryBlockIterator,
    RetryAttemptContext,
    RetryBlockIterator,
)
from relinker.context.async_ import (
    AsyncRetryAttemptContext as AsyncRetryAttemptContextFromModule,
)
from relinker.context.async_ import AsyncRetryBlockIterator as AsyncRetryBlockIteratorFromModule
from relinker.context.sync import RetryAttemptContext as RetryAttemptContextFromModule
from relinker.context.sync import RetryBlockIterator as RetryBlockIteratorFromModule


def test_context_exports_are_ordered() -> None:
    assert context.__all__ == [
        "AsyncRetryAttemptContext",
        "AsyncRetryBlockIterator",
        "RetryAttemptContext",
        "RetryBlockIterator",
    ]


def test_context_sync_exports_preserve_identity() -> None:
    assert RetryAttemptContext is RetryAttemptContextFromModule
    assert RetryBlockIterator is RetryBlockIteratorFromModule


def test_context_async_exports_preserve_identity() -> None:
    assert AsyncRetryAttemptContext is AsyncRetryAttemptContextFromModule
    assert AsyncRetryBlockIterator is AsyncRetryBlockIteratorFromModule


def test_root_exports_preserve_identity() -> None:
    assert relinker.RetryAttemptContext is RetryAttemptContext
    assert relinker.AsyncRetryAttemptContext is AsyncRetryAttemptContext


def test_policy_iter_uses_reexported_types() -> None:
    iterator = RetryPolicy().attempts(1).iter(name="package_test")

    assert isinstance(iterator, RetryBlockIterator)
    attempt = next(iterator)
    assert isinstance(attempt, RetryAttemptContext)
    assert attempt.number == 1
    assert iterator.name == "package_test"


@pytest.mark.asyncio
async def test_policy_async_iter_uses_reexported_types() -> None:
    iterator = RetryPolicy().attempts(1).async_iter(name="async_package_test")

    assert isinstance(iterator, AsyncRetryBlockIterator)
    attempt = await iterator.__anext__()
    assert isinstance(attempt, AsyncRetryAttemptContext)
    assert attempt.number == 1
    assert iterator.name == "async_package_test"


def test_iterator_attributes_remain_readable() -> None:
    sync_iterator = RetryPolicy().attempts(1).iter(name="sync_attrs")
    async_iterator = RetryPolicy().attempts(1).async_iter(name="async_attrs")

    for iterator in (sync_iterator, async_iterator):
        assert isinstance(iterator.started_at, float)
        assert tuple(iterator.attempts) == ()
        assert iterator.attempt_number == 0
        assert iterator.finished is False
        assert iterator.result is None
        assert iterator.outcome is None
        assert iterator.has_outcome is False
        assert isinstance(iterator.policy, RetryPolicy)
        assert iterator.name in {"sync_attrs", "async_attrs"}


def test_context_module_is_a_package() -> None:
    assert hasattr(context, "__path__")
