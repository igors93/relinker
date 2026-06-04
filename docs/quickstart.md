# Quickstart

This guide shows the smallest useful RetryFlow examples.

## Install from GitHub

Until RetryFlow is published on PyPI:

```bash
pip install git+https://github.com/igors93/retryflow.git
```

For local development:

```bash
git clone https://github.com/igors93/retryflow.git
cd retryflow
pip install -e ".[dev]"
```

## Basic decorator

```python
from retryflow import retry

@retry(attempts=3, delay=1)
def fetch_data() -> str:
    return "ok"
```

## Retry on specific exceptions

```python
from retryflow import retry

@retry(attempts=5, delay=0.5, on=(TimeoutError, ConnectionError))
def call_api() -> str:
    return "response"
```

## Fluent policy

```python
from retryflow import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
)

@policy
def call_api() -> str:
    return "response"
```

## Return RetryResult

Use `return_result()` when you want to inspect what happened.

```python
from retryflow import RetryPolicy

result = (
    RetryPolicy()
    .attempts(3)
    .return_result()
    .run(lambda: "ok")
)

print(result.succeeded)
print(result.attempt_count)
print(result.story())
```

## Retry by returned value

```python
from retryflow import RetryPolicy

result = (
    RetryPolicy()
    .attempts(3)
    .retry_if_result(lambda value: value is None)
    .return_result()
    .run(lambda: None)
)

print(result.failed)
print(result.exhausted)
print(result.exhausted_by_result)
```

## Async usage

```python
import asyncio
from retryflow import retry

@retry(attempts=3)
async def fetch_async() -> str:
    return "ok"

async def main() -> None:
    print(await fetch_async())

asyncio.run(main())
```

## Debug mode

```python
from retryflow import RetryPolicy

policy = RetryPolicy().attempts(3).debug()

@policy
def task() -> str:
    return "ok"
```
