import pytest

from relinker import RetryPolicy
from relinker.exceptions import RetryExhaustedError


@pytest.mark.asyncio
async def test_async_executor_return_result() -> None:
    async def task() -> str:
        return "ok"

    result = await RetryPolicy().attempts(1).return_result().run_async(task)

    assert result.succeeded
    assert result.value == "ok"


@pytest.mark.asyncio
async def test_async_executor_does_not_swallow_keyboard_interrupt() -> None:
    async def task() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        await RetryPolicy().attempts(3).return_result().run_async(task)


@pytest.mark.asyncio
async def test_async_executor_marks_result_exhaustion_when_returning_result() -> None:
    async def task() -> None:
        return None

    result = (
        await RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value is None)
        .return_result()
        .run_async(task)
    )

    assert result.failed
    assert result.exhausted
    assert result.exhausted_by_result
    assert result.value is None


@pytest.mark.asyncio
async def test_async_executor_can_raise_on_result_exhaustion() -> None:
    async def task() -> None:
        return None

    policy = (
        RetryPolicy()
        .attempts(2)
        .retry_if_result(lambda value: value is None)
        .raise_on_result_exhausted()
    )

    with pytest.raises(RetryExhaustedError):
        await policy.run_async(task)
