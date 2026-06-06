from typing import cast

from relinker import RetryPolicy, retry


@retry(attempts=2, delay=0, on=(TimeoutError,))
async def fetch_value(value: int) -> int:
    return value


async def use_async_policy() -> int:
    policy: RetryPolicy[int] = RetryPolicy[int]().attempts(2).on(TimeoutError).no_delay()
    direct = cast(int, await policy.run_async(fetch_value, 42))
    decorated = await fetch_value(1)
    return direct + decorated
