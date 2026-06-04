"""No-sleep helpers for tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from retryflow.policy import RetryPolicy


def _do_not_sleep(seconds: float) -> None:
    """Ignore sync sleep during tests."""


async def _do_not_sleep_async(seconds: float) -> None:
    """Ignore async sleep during tests."""


@contextmanager
def no_sleep(policy: RetryPolicy) -> Iterator[RetryPolicy]:
    """
    Yield a copy of the policy with sync and async sleep disabled.

    This helper is a context manager for readability, even though the policy is
    immutable and does not need cleanup.
    """
    yield policy.with_sleep(_do_not_sleep, _do_not_sleep_async)


def no_sleep_async(policy: RetryPolicy) -> RetryPolicy:
    """Return a copy of the policy with async sleep disabled."""
    return policy.with_sleep(_do_not_sleep, _do_not_sleep_async)
