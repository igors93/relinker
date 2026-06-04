# Quickstart

Relinker has three levels of usage:

1. `@retry` for simple cases.
2. Presets for common production scenarios.
3. `RetryPolicy` for full control.

## Install from GitHub

Until Relinker is published on PyPI:

```bash
pip install git+https://github.com/igors93/relinker.git
```

For local development:

```bash
git clone https://github.com/igors93/relinker.git
cd relinker
pip install -e ".[dev]"
```

## Simple decorator

```python
from relinker import retry

@retry(attempts=3, delay=1)
def fetch_data() -> str:
    return "ok"
```

## Preset

```python
from relinker import network

@network()
def call_api() -> str:
    return "response"
```

## Fluent policy

```python
from relinker import RetryPolicy

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
from relinker import RetryPolicy

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

## Diagnostics

```python
policy = RetryPolicy().forever().on(Exception).no_delay()

for warning in policy.warnings():
    print(warning.code, warning.message)

print(policy.timeline(attempts=3))
```
