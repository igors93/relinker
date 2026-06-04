import asyncio

from retryflow import retry


@retry(attempts=3)
async def async_task() -> str:
    return "ok"


async def main() -> None:
    print(await async_task())


asyncio.run(main())
