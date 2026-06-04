# RetryFlow

RetryFlow is a Python retry library focused on clarity, control, and debuggability.

It gives you:

- A simple `@retry` decorator.
- A fluent `RetryPolicy` builder.
- Sync and async execution.
- Retry by exception, result, or custom condition.
- Fixed, exponential, random, and custom delays.
- Rich execution results.
- Events for logging and observability.
- Testing helpers to avoid real sleeping in tests.

## Installation

```bash
pip install retryflow
```

For local development:

```bash
pip install -e ".[dev]"
```

## Quick example

```python
from retryflow import retry

@retry(attempts=3, delay=1)
def unstable_task() -> str:
    return "ok"

print(unstable_task())
```

## Policy example

```python
from retryflow import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
    .debug()
)

@policy
def fetch_data() -> str:
    return "data"
```

## Design goal

RetryFlow does not try to control your application.  
It only prevents impossible configurations and gives you tools to understand exactly what will happen.
