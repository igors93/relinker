# Getting Started

## What is retry?

Some failures are temporary. A network timeout, a brief database hiccup, or a
short-lived rate limit response might succeed if tried again a few seconds later.

Some failures are permanent. A wrong password, an invalid email address, or a
deleted resource will not improve with repetition — retrying wastes time and
delays the error.

Retry is useful only when there is a reasonable chance the next attempt will
succeed. Relinker helps you express exactly which failures to retry, how long to
wait, and what to do when all attempts run out.

---

## Install

From PyPI:

```bash
pip install relinker
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

See [Installation](installation.md) for GitHub, source, and verification
options.

---

## The smallest useful retry

```python
from relinker import retry

@retry(attempts=3, delay=1, on=(TimeoutError,))
def fetch_data() -> str:
    return call_external_service()
```

If `fetch_data()` raises `TimeoutError`, Relinker tries again — up to 3 total
calls — and waits 1 second between attempts. Any other exception propagates
immediately without retrying.

---

## Use a preset

Presets cover common scenarios with sensible defaults:

```python
from relinker import network

@network()
def call_api() -> str:
    return client.get("/users/1")
```

Presets return ordinary `RetryPolicy` objects, so you can keep customizing them:

```python
policy = network().attempts(8).fallback_value({"status": "offline"})
```

---

## Fluent policy

For full control, use the builder directly:

```python
from relinker import RetryPolicy

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
)

value = policy.run(fetch_data)
```

Each line adds one constraint:
- `.attempts(5)` — allow up to 5 total calls;
- `.on(TimeoutError, ConnectionError)` — retry only these exceptions;
- `.exponential_delay(base=1, maximum=30)` — wait 1, 2, 4, 8 … seconds, capped at 30;
- `.jitter(maximum=0.5)` — add up to 0.5s random variation to prevent synchronized retries.

---

## Before production

Always inspect policies before they affect real services:

```python
print(policy.explain())         # plain-language description
print(policy.preview(attempts=5))  # estimated timing
print(policy.doctor().describe())  # known risks
```

This is the main difference between Relinker and a hidden retry loop: Relinker
helps you understand what will happen before it happens.

---

## Next steps

- [Choosing a policy](choosing-a-policy.md) — decision guide by situation
- [Policy builder](policy-builder.md) — full method reference
- [Retry lifecycle](../concepts/retry-lifecycle.md) — how one execution flows
- [Production checklist](production-checklist.md) — review before deploying
- [When not to retry](when-not-to-retry.md) — when retry causes more harm
