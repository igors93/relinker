import asyncio

from retryflow import network


@network()
async def fetch_user() -> dict[str, int]:
    return {"id": 1}


async def main() -> None:
    print(await fetch_user())


if __name__ == "__main__":
    asyncio.run(main())
