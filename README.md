<div align="center">

# Relinker

[![CI](https://github.com/igors93/relinker/actions/workflows/ci.yml/badge.svg)](https://github.com/igors93/relinker/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-stable-brightgreen)
![Typing](https://img.shields.io/badge/typing-typed-blue)
![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

**Simple by default, powerful by composition, safe by guidance.**

Relinker is a clear, modular, and debuggable retry library for Python.  
It helps you retry temporary failures without hiding what your code is doing.

[Overview](#overview) · [Features](#features) · [Quick Start](#quick-start) · [Guidance](#guidance) · [HTTP](#http-retry) · [Observability](#observability) · [Examples](#examples) · [Documentation](#documentation)

</div>

---

## Overview

Applications fail for reasons that are often temporary:

- a network timeout
- a busy API
- a database connection hiccup
- a rate limit response
- a background job that should be tried again

Relinker gives you a clean way to describe what should happen:

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
)
```

This reads like a sentence:

> Try up to 5 times, retry only on timeout or connection errors, wait with exponential backoff, and add jitter.

---

## Features

Relinker currently provides:

- simple `@retry` decorator
- fluent `RetryPolicy` builder
- shared, process-local `RetryBudget` protection against retry storms
- sync and async execution
- retry by exception, returned result, or custom condition
- fixed, linear, chain, exponential, random, randomized exponential, custom, additive, and state-aware delays
- composable stop strategies
- composable retry conditions
- built-in presets for common situations
- rich `RetryResult` objects
- per-function retry statistics
- `warnings()` for risky policies
- `doctor()` health reports
- `simulate()`, `timeline()`, `preview()`, and `explain()`
- safe structured logging
- event hooks for observability
- HTTP retry helpers with `Retry-After` support
- context manager support for retrying blocks
- testing support through custom sleep functions
- zero required runtime dependencies

---

## Current status

Relinker 1.0 provides a stable public API for Python 3.10 through 3.13.
Compatibility guarantees apply to the documented exports and behaviors described
in the [compatibility policy](docs/reference/compatibility.md). Release history lives in
[`CHANGELOG.md`](CHANGELOG.md).

See the [migration guide](docs/guides/migrating-to-1.0.md) if you are upgrading
from an earlier version.

Install from PyPI:

```bash
pip install relinker
```

For development or to track the latest changes on the main branch:

```bash
pip install git+https://github.com/igors93/relinker.git
```

For local development:

```bash
git clone https://github.com/igors93/relinker.git
cd relinker
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

---

## Quick Start

### The smallest useful retry

```python
from relinker import retry

@retry(attempts=3, delay=1, on=(TimeoutError,))
def fetch_data() -> str:
    return call_external_service()
```

If `fetch_data()` raises `TimeoutError`, Relinker tries again up to 3 times and waits 1 second between attempts.

### Use a preset

```python
from relinker import network

@network()
def call_api() -> dict:
    return client.get("/users/1")
```

Presets are regular policies. You can keep customizing them:

```python
policy = network().attempts(8).fallback_value({"status": "offline"})
```

### Share a retry budget

A retry budget limits additional attempts across executions that share the same
budget object and key. The original attempt is never counted.

```python
from relinker import RetryBudget, RetryPolicy

budget = RetryBudget(max_retries=20, per=60)

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError)
    .exponential_delay(base=1, maximum=30)
    .with_retry_budget(budget, key="external-api")
)
```

`RetryBudget` is in-memory and process-local. Separate processes do not share
capacity. Normal policy delays and `max_time()` continue to apply. See
[Retry budgets](docs/concepts/retry-budgets.md) for the complete behavior and scope.

### Use the full builder

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
    .fallback_value({"status": "unavailable"})
)

result = policy.run(fetch_data)
```

---

## Guidance

Relinker does not try to control your application. It lets you make your own choices, but it helps you notice risky retry policies.

```python
from relinker import RetryPolicy

policy = RetryPolicy().forever().on(Exception).no_delay()

print(policy.doctor().describe())
```

Example output:

```text
Relinker policy health

Risk level: risky

Warnings:
- forever: This policy can retry forever.
- no_delay: This policy has no delay between attempts.
- tight_loop_risk: This policy can retry forever without sleeping.
- broad_exception: This policy retries all Exception subclasses.
```

Use `explain()` when you want to understand a policy in plain language:

```python
print(policy.explain())
```

Use `preview()` when you want to estimate timing before running real code:

```python
print(policy.preview(attempts=5))
```

---

## HTTP retry

Relinker includes dependency-free HTTP helpers. They work with any response object that exposes `.status_code` or a dictionary with a `"status_code"` key.

```python
from relinker import http_retry_policy

policy = http_retry_policy(
    attempts=5,
    statuses={429, 500, 502, 503, 504},
    respect_retry_after=True,
)
```

For lower-level control:

```python
from relinker import RetryPolicy, retry_after_delay, retry_if_status

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 500, 502, 503, 504}))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
)
```

This is useful for APIs that return `429 Too Many Requests` with a `Retry-After` header.

---

## Observability

### Human-readable logging

```python
import logging
from relinker import RetryPolicy

logging.basicConfig(level=logging.INFO)

policy = RetryPolicy().attempts(3).on(TimeoutError).with_logging(level=logging.INFO)
```

### Structured logging

```python
policy = RetryPolicy().attempts(3).on(TimeoutError).with_structured_logging()
```

Structured logs exclude error messages by default because exception messages can contain tokens, URLs, payload fragments, or user data.

### Events

```python
from relinker import RetryEvent, RetryPolicy

def on_retry(event: RetryEvent) -> None:
    print(f"retrying after attempt {event.attempt_number}, delay={event.delay}")

policy = RetryPolicy().attempts(3).on(TimeoutError).on_retry(on_retry)
```

---

## Results and statistics

Return a `RetryResult` when you want full visibility:

```python
result = RetryPolicy().attempts(3).return_result().run(fetch_data)

print(result.summary())
print(result.story())
```

Decorated functions also receive retry statistics:

```python
from relinker import network

@network()
def fetch_user() -> dict:
    return {"id": 1}

fetch_user()

print(fetch_user.retry_stats.to_dict())
```

---

## Examples

Run examples from the project root:

```bash
python -m examples.basic_retry
python -m examples.retry_with_policy
python -m examples.retry_policy_doctor
python -m examples.retry_preview_and_explain
python -m examples.retry_http_retry_after
python -m examples.retry_structured_logging
```

See [`examples/README.md`](examples/README.md) for the full list.

---

## Documentation

The documentation is organized by topic:

- [Documentation index](docs/README.md)
- [Getting started](docs/guides/getting-started.md)
- [Retry lifecycle](docs/concepts/retry-lifecycle.md)
- [Exhaustion behavior](docs/concepts/exhaustion.md)
- [Policy builder](docs/guides/policy-builder.md)
- [Retry budgets](docs/concepts/retry-budgets.md)
- [Diagnostics and guidance](docs/guides/diagnostics.md)
- [HTTP retry](docs/guides/http.md)
- [Observability](docs/guides/observability.md)
- [Results and statistics](docs/concepts/results.md)
- [Context manager usage](docs/guides/context-manager.md)
- [Testing retry code](docs/guides/testing.md)
- [API reference](docs/reference/api.md)
- [Compatibility policy](docs/reference/compatibility.md)
- [Architecture](docs/maintainers/architecture.md)
- [Production checklist](docs/guides/production-checklist.md)

---

## Development checks

```bash
./scripts/ci.sh
```

Or run each step:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest
python -m build
```

---

## Design principles

Relinker is guided by these principles:

1. Simple things should be simple.
2. Advanced things should be possible.
3. Code should be readable and modular.
4. Names should be intuitive.
5. Defaults should be safe.
6. Dangerous policies should produce warnings.
7. The user stays in control.
8. Debugging should be built in.
9. No unnecessary magic.
10. Production behavior should be explainable.

---

## License

MIT.
