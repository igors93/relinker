# RetryFlow

[![CI](https://github.com/igors93/retryflow/actions/workflows/ci.yml/badge.svg)](https://github.com/igors93/retryflow/actions/workflows/ci.yml)

RetryFlow is a Python retry library focused on clarity, control, and debuggability.

It gives you:

- A simple `@retry` decorator.
- Ready-to-use presets such as `network()`, `database()`, and `background_job()`.
- A fluent `RetryPolicy` builder.
- Sync and async execution.
- Retry by exception, result, or custom condition.
- Fixed, linear, chain, exponential, random, random exponential, custom, and additive delays.
- Composable retry conditions.
- Composable stop strategies.
- Rich execution results.
- Per-function retry statistics.
- Policy diagnostics with `warnings()` and `simulate()`.
- Better exhausted-retry handling with fallbacks and custom exceptions.
- Event state for logging and observability.
- Context manager support for retrying blocks.
- Testing helpers to avoid real sleeping in tests.

## Current status

RetryFlow is in early development. The current package version is `0.4.0`.

Until the package is published on PyPI, install it directly from GitHub:

```bash
pip install git+https://github.com/igors93/retryflow.git
```

## Simple usage

Use `@retry` for quick cases:

```python
from retryflow import retry

@retry(attempts=3, delay=1)
def unstable_task() -> str:
    return "ok"
```

Use presets for common production scenarios:

```python
from retryflow import network

@network()
def call_external_api() -> str:
    return "response"
```

Use `RetryPolicy` when you want full control:

```python
from retryflow import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
)
```

## Diagnostics

RetryFlow does not block application-level choices, but it can help users notice
risky policies.

```python
policy = RetryPolicy().forever().on(Exception).no_delay()

for warning in policy.warnings():
    print(warning.code, warning.message)

print(policy.simulate(attempts=5).describe())
```

## Statistics

Decorated functions receive retry statistics:

```python
from retryflow import network

@network()
def fetch_data() -> str:
    return "ok"

fetch_data()

print(fetch_data.retry_stats.to_dict())
```

## Exhausted retry control

```python
policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .fallback_value({"status": "unavailable"})
)
```

Or raise a custom exception:

```python
class ServiceUnavailableError(RuntimeError):
    pass

policy = (
    RetryPolicy()
    .attempts(3)
    .on(TimeoutError)
    .on_exhausted_raise(ServiceUnavailableError)
)
```

## Async

```python
from retryflow import network

@network()
async def fetch_user() -> dict:
    return {"id": 1}
```

## Development checks

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
