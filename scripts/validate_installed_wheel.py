"""Validate core Relinker behavior from an installed wheel."""

from __future__ import annotations

import asyncio
from importlib.metadata import version as distribution_version
from pathlib import Path
from typing import Any

import relinker
from relinker import RetryBudget, RetryPolicy, retry


def _assert_installed_distribution() -> None:
    module_file = Path(relinker.__file__).resolve()
    repository_root = Path(__file__).resolve().parents[1]
    source_package = (repository_root / "src" / "relinker").resolve()

    assert source_package not in module_file.parents, (
        "validation imported Relinker from the source tree instead of the installed wheel"
    )


def _validate_public_api() -> None:
    for name in relinker.__all__:
        value: Any = getattr(relinker, name)
        assert value is not None

    assert isinstance(relinker.__version__, str)
    assert relinker.__version__
    assert relinker.__version__ == "1.0.1"
    assert distribution_version("relinker") == "1.0.1"


def _validate_sync_run() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TimeoutError("temporary")
        return "ok"

    result = RetryPolicy[str]().attempts(3).on(TimeoutError).no_delay().run(operation)

    assert result == "ok"
    assert calls == 3


def _validate_decorator() -> None:
    calls = 0

    @retry(attempts=2, delay=0, on=(TimeoutError,))
    def operation() -> int:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise TimeoutError("temporary")
        return 42

    assert operation() == 42
    assert calls == 2


async def _validate_async_run() -> None:
    calls = 0

    async def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise TimeoutError("temporary")
        return "async-ok"

    result = await RetryPolicy[str]().attempts(2).on(TimeoutError).no_delay().run_async(operation)

    assert result == "async-ok"
    assert calls == 2


def _validate_sync_context_manager() -> None:
    calls = 0
    policy = RetryPolicy[str]().attempts(2).on(TimeoutError).no_delay()
    iterator = policy.iter(name="wheel_sync_context")

    for attempt in iterator:
        with attempt:
            calls += 1
            if calls < 2:
                raise TimeoutError("temporary")
            attempt.set_result("context-ok")

    assert calls == 2
    assert iterator.result is not None
    assert iterator.result.succeeded is True
    assert iterator.result.value == "context-ok"


async def _validate_async_context_manager() -> None:
    calls = 0
    policy = RetryPolicy[str]().attempts(2).on(TimeoutError).no_delay()
    iterator = policy.async_iter(name="wheel_async_context")

    async for attempt in iterator:
        async with attempt:
            calls += 1
            if calls < 2:
                raise TimeoutError("temporary")
            attempt.set_result("async-context-ok")

    assert calls == 2
    assert iterator.result is not None
    assert iterator.result.succeeded is True
    assert iterator.result.value == "async-context-ok"


def _validate_retry_budget() -> None:
    calls = 0
    budget = RetryBudget(max_retries=2, per=60)
    policy = (
        RetryPolicy[str]()
        .attempts(2)
        .on(TimeoutError)
        .no_delay()
        .with_retry_budget(budget, key="wheel-smoke")
    )

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise TimeoutError("temporary")
        return "budget-ok"

    result = policy.run(operation)

    assert result == "budget-ok"
    assert calls == 2


async def _validate_async_scenarios() -> None:
    await _validate_async_run()
    await _validate_async_context_manager()


def main() -> None:
    _assert_installed_distribution()
    _validate_public_api()
    _validate_sync_run()
    _validate_decorator()
    _validate_sync_context_manager()
    _validate_retry_budget()
    asyncio.run(_validate_async_scenarios())

    print(
        "Installed wheel validation passed for Relinker 1.0.1: public API, sync, async, "
        "decorator, context managers, and Retry Budget."
    )


if __name__ == "__main__":
    main()
