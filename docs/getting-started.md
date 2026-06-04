# Getting Started

RetryFlow helps Python applications retry temporary failures in a way that is easy to read and easy to reason about.

## Install

From GitHub:

```bash
pip install git+https://github.com/igors93/retryflow.git
```

For local development:

```bash
git clone https://github.com/igors93/retryflow.git
cd retryflow
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Basic decorator

```python
from retryflow import retry

@retry(attempts=3, delay=1, on=(TimeoutError,))
def fetch_data() -> str:
    return call_external_service()
```

This retries `fetch_data()` up to 3 times when it raises `TimeoutError`.

## Preset policy

```python
from retryflow import network

@network()
def call_api() -> str:
    return "ok"
```

Presets are shortcuts for common production scenarios. They return normal `RetryPolicy` objects, so they can still be customized.

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

value = policy.run(fetch_data)
```

## Before production

Always inspect policies that may affect external services:

```python
print(policy.explain())
print(policy.preview(attempts=5))
print(policy.doctor().describe())
```

This is the main difference between RetryFlow and a hidden retry loop: RetryFlow helps you understand what will happen.
