from __future__ import annotations

import asyncio

from retryflow import RetryPolicy

attempts = 0


async def fetch_data() -> str:
    global attempts
    attempts += 1
    if attempts < 3:
        raise TimeoutError("temporary async timeout")
    return "ok"


policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(0.1)


async def main() -> None:
    print(await policy.run_async(fetch_data))


if __name__ == "__main__":
    asyncio.run(main())
