# Async

Relinker supports async functions and async retry blocks.

## Async decorator

```python
from relinker import retry

@retry(attempts=3)
async def fetch_user() -> dict:
    return {"id": 1}
```

## Async policy

```python
from relinker import RetryPolicy

policy = RetryPolicy().attempts(3).on(TimeoutError)

@policy
async def fetch_user() -> dict:
    return {"id": 1}
```

## Manual async run

```python
result = await (
    RetryPolicy()
    .attempts(3)
    .return_result()
    .run_async(fetch_user)
)
```

## Async context manager

```python
policy = RetryPolicy().attempts(3).on(TimeoutError)

async for attempt in policy.async_iter(name="external_service"):
    async with attempt:
        await call_service()
```

## Custom async sleep

Relinker uses `asyncio.sleep` by default. You can provide your own async sleep
function for advanced runtimes or tests.

```python
async def custom_sleep(seconds: float) -> None:
    await some_async_sleep(seconds)

policy = RetryPolicy().with_sleep(
    sleep=lambda seconds: None,
    async_sleep=custom_sleep,
)
```

The core package does not depend on Trio, AnyIO, or Tornado. This keeps Relinker
small and lets users integrate the async runtime they prefer.
