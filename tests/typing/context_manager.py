from relinker import RetryPolicy


def use_sync_context() -> str:
    policy: RetryPolicy[str] = RetryPolicy[str]().attempts(1)
    for attempt in policy:
        with attempt:
            attempt.set_result("ok")
    return "ok"


async def use_async_context() -> str:
    policy: RetryPolicy[str] = RetryPolicy[str]().attempts(1)
    async for attempt in policy:
        async with attempt:
            attempt.set_result("ok")
    return "ok"
