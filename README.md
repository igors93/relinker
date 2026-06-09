<div align="center">

# Relinker

[![CI](https://github.com/igors93/relinker/actions/workflows/ci.yml/badge.svg)](https://github.com/igors93/relinker/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-stable-brightgreen)
![Typing](https://img.shields.io/badge/typing-typed-blue)
![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

**A retry library that shows you exactly what it is doing — and warns you when something looks risky.**

</div>

```python
from relinker import retry

@retry(attempts=3, delay=1, on=(TimeoutError,))
def fetch_data() -> str:
    return call_external_service()
```

Three total calls. Waits 1 second between attempts. Retries only `TimeoutError`.
When all attempts fail, the last exception propagates normally.

The same policy scales to a full production configuration — see [Quick Start](#quick-start) below.

---

## Install

```bash
pip install relinker
```

Requires Python 3.10+. No runtime dependencies.

For local development:

```bash
git clone https://github.com/igors93/relinker.git
cd relinker
python -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
```

---

## What it does

**Describe the policy, not the loop.** Relinker separates *what* should retry from *how* it runs. Policies are immutable objects — compose them, share them, inspect them.

**Guidance built in.** `warnings()` and `doctor()` flag risky configurations like infinite retry without delay or retrying all exceptions. You keep full control; Relinker just points things out.

**Full visibility.** `RetryResult` records every attempt, timing, and error type. `simulate()` and `timeline()` estimate behaviour before production. Structured logging excludes exception messages by default to avoid leaking sensitive data.

**Sync and async, same API.** Decorate a regular function or a coroutine function — the same policy works for both.

**Zero required dependencies.** The core package has no runtime requirements. HTTP helpers, presets, and testing utilities are included.

---

## Features at a glance

| Category | What's included |
|---|---|
| **Entry points** | `@retry` decorator · fluent `RetryPolicy` builder · presets (`network`, `database`, `fast`, …) |
| **Stop strategies** | by attempt count · by elapsed time · forever · composable AND / OR |
| **Retry conditions** | by exception type · by returned value · custom callback · `TryAgain` signal |
| **Delays** | fixed · linear · exponential · random · chain · state-aware · jitter · custom |
| **HTTP helpers** | `Retry-After` support · status-code conditions · `http_retry_policy()` |
| **Shared capacity** | `RetryBudget` — process-local, per-key rolling window |
| **Results** | `RetryResult` · attempt history · per-function statistics |
| **Observability** | structured logging · event hooks · `debug()` |
| **Guidance** | `warnings()` · `doctor()` · `explain()` · `simulate()` · `timeline()` · `preview()` |
| **Execution** | sync `run()` · async `run_async()` · sync/async context managers |
| **Testing** | `for_testing()` · custom sleep injection · sleep capture |

---

## Stability

Relinker 1.0 introduced a stable public API. Relinker 1.x continues that stability and currently supports Python 3.10 through Python 3.14.
Compatibility guarantees cover the documented exports and behaviors described in
the [compatibility policy](docs/reference/compatibility.md). Release history lives in
[`CHANGELOG.md`](CHANGELOG.md).

See the [migration guide](docs/guides/migrating-to-1.0.md) when upgrading from
an earlier version.

---

## Quick Start

The same retry idea scales from a one-line decorator to a complete production policy.
`retry()`, presets, and `RetryPolicy` are three entry points to the same runtime — not
separate tiers.

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

### Grow into a production policy

When the configuration outgrows one line, build it explicitly.
Each method adds one constraint; the result is a reusable, inspectable object:

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

Before this reaches production, ask Relinker what it will do:

```python
print(policy.explain())           # plain-language description
print(policy.preview(attempts=5)) # estimated timing per attempt
print(policy.doctor().describe()) # flagged risks, if any
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

Relinker includes dependency-free HTTP helpers. They work with any response object that exposes `.status_code` or a dictionary with a `"status_code"` key. Transport exceptions are opt-in so existing `1.x` result-based HTTP policies keep their behavior.

```python
from relinker import DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS, http_retry_policy

policy = http_retry_policy(
    attempts=5,
    statuses={429, 500, 502, 503, 504},
    transport_exceptions=DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS,
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
from relinker import RetryPolicy
from relinker.event import RetryEvent

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

Detailed result output preserves exception messages by default for compatibility.
When the output may be stored in logs or telemetry, exclude those messages
explicitly:

```python
print(result.story(include_error_message=False))
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

| | |
|---|---|
| [Getting started](docs/guides/getting-started.md) | Install and write your first policy |
| [Choosing a policy](docs/guides/choosing-a-policy.md) | Decision guide by situation |
| [Feature map](docs/reference/feature-map.md) | Quick lookup: need → API |
| [When not to retry](docs/guides/when-not-to-retry.md) | Idempotency, generators, permanent failures |
| [Common mistakes](docs/guides/common-mistakes.md) | Risky patterns with safer alternatives |
| [Troubleshooting](docs/guides/troubleshooting.md) | Symptom-by-symptom diagnosis |
| [Production checklist](docs/guides/production-checklist.md) | Review before deploying |
| [Retry lifecycle](docs/concepts/retry-lifecycle.md) | How one execution flows |
| [Retry budgets](docs/concepts/retry-budgets.md) | Shared capacity explained |
| [HTTP retry](docs/guides/http.md) | Status codes and `Retry-After` |
| [Testing](docs/guides/testing.md) | Keep tests fast and deterministic |
| [API reference](docs/reference/api.md) | Full method and export reference |
| [Compatibility policy](docs/reference/compatibility.md) | Stability guarantees |

Full index: [docs/README.md](docs/README.md)

---

## Contributing

Bug reports, questions, and pull requests are welcome.

- Read [CONTRIBUTING.md](CONTRIBUTING.md) for local setup, code principles, and the pull request process.
- Open an issue to report a bug or propose a feature before writing code.
- Keep changes small and focused — one behaviour change per pull request.
- Every bug fix needs a regression test. Coverage must not decrease.

---

## Security

Relinker validates all numeric inputs at construction time and caps
`Retry-After` header values to prevent unexpectedly long sleeps.

To report a vulnerability, open a private security advisory on GitHub.
Do not publish sensitive details publicly before the issue is reviewed.

See [SECURITY.md](SECURITY.md) for the full security policy.

---

## License

MIT.
