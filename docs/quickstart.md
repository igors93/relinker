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

## Fluent policy

```python
from retryflow import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
)

@policy
def call_api() -> str:
    return "response"
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
print(result.exhausted_by_result)
```

## Context manager

```python
from retryflow import RetryPolicy

policy = RetryPolicy().attempts(3).on(RuntimeError)

for attempt in policy.iter(name="database_block"):
    with attempt:
        save_to_database()
```

## Context manager with result retry

```python
from retryflow import RetryPolicy

policy = RetryPolicy().attempts(3).retry_if_result(lambda value: value is None)

for attempt in policy.iter(name="result_block"):
    with attempt:
        value = maybe_return_none()
        attempt.set_result(value)
```

## Async context manager

```python
from retryflow import RetryPolicy

policy = RetryPolicy().attempts(3).on(TimeoutError)

async for attempt in policy.async_iter(name="async_block"):
    async with attempt:
        await call_async_service()
```
