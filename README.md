# RetryFlow

[![CI](https://github.com/igors93/retryflow/actions/workflows/ci.yml/badge.svg)](https://github.com/igors93/retryflow/actions/workflows/ci.yml)

RetryFlow is a Python retry library focused on clarity, control, and debuggability.

It gives you:

- A simple `@retry` decorator.
- A fluent `RetryPolicy` builder.
- Sync and async execution.
- Retry by exception, result, or custom condition.
- Fixed, exponential, random, custom, and additive delays.
- Composable retry conditions.
- Composable stop strategies.
- Rich execution results.
- Event state for logging and observability.
- Context manager support for retrying blocks.
- Testing helpers to avoid real sleeping in tests.

## Current status

RetryFlow is in early development.

Until the package is published on PyPI, install it directly from GitHub:

```bash
pip install git+https://github.com/igors93/retryflow.git
```

For local development:

```bash
git clone https://github.com/igors93/retryflow.git
cd retryflow
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
    .jitter(maximum=0.5)
    .debug()
)

@policy
def fetch_data() -> str:
    return "data"
```

## Result-aware retry

```python
from retryflow import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(3)
    .retry_if_result(lambda value: value is None)
    .return_result()
)

result = policy.run(lambda: None)

print(result.failed)
print(result.exhausted)
print(result.story())
```

## Context manager

```python
from retryflow import RetryPolicy

policy = RetryPolicy().attempts(3).on(RuntimeError)

for attempt in policy.iter(name="important_block"):
    with attempt:
        risky_operation()
```

## Development checks

Run the same checks used by GitHub Actions:

```bash
./scripts/ci.sh
```

## Design goal

RetryFlow does not try to control your application.

It only prevents impossible or dangerous library-level behavior, such as:

- negative attempts
- negative delays
- invalid exception types
- swallowing `KeyboardInterrupt` or `SystemExit`

The user remains in control of application-level decisions.
