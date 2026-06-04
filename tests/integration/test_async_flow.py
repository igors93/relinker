import pytest

from relinker import RetryPolicy


@pytest.mark.asyncio
async def test_async_flow() -> None:
    async def task() -> str:
        return "ok"

    value = await RetryPolicy().attempts(1).run_async(task)

    assert value == "ok"


@pytest.mark.asyncio
async def test_async_flow_result_exhaustion() -> None:
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
    assert result.exhausted_by_result
    assert result.attempt_count == 2
