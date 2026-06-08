# When Not to Retry

Retry is not the right tool for every failure. Used in the wrong place, it
delays the error response, hides real problems, and can cause duplicate side
effects.

---

## Non-idempotent operations

*Idempotent* means: repeating the operation produces the same final state as
doing it once. Reading a user profile is idempotent — it does not change anything.

Charging a card is not idempotent by default — two charges produce two
transactions.

### HTTP methods

Conventionally safe to retry:

- `GET` — fetches data
- `HEAD` — fetches metadata
- `PUT` — replaces a resource entirely
- `DELETE` — removes a resource
- `OPTIONS` — asks about capabilities

Review carefully before retrying:

- `POST` — creates a new resource or triggers a side effect
- `PATCH` — applies a partial update

A `POST /payments` that times out before a response arrives may have already
succeeded on the server. Retrying creates a second charge.

### Safeguards for non-idempotent operations

Relinker does not implement these safeguards — they belong to the application or
the service:

- **Idempotency key:** send a unique ID with each request; the server ignores
  duplicates.
- **Unique transaction ID:** the same request ID is recognized as a replay, not
  a new charge.
- **Server confirmation:** before retrying, query the server whether the
  original attempt succeeded.

If the server does not support any of these, do not retry the operation
automatically.

### Examples where idempotency matters

| Operation | Idempotent? | Risk if retried without safeguards |
|---|---|---|
| Read account balance | Yes | None |
| Search for products | Yes | None |
| Create an order | No | Duplicate orders |
| Charge a payment | No | Duplicate charge |
| Send an email | No | Duplicate email |
| Upload a file | Depends | Depends on API design |
| Update user name | Yes (if full replace) | Harmless duplication |

---

## Permanent failures

Some failures cannot resolve by waiting. Retrying them wastes time and delays
the error response.

Do not retry:

- **Validation errors:** `400 Bad Request`, missing required field, invalid
  format. The request is wrong; sending it again returns the same error.
- **Authentication errors:** `401 Unauthorized`. The credentials are invalid
  and will not become valid by waiting.
- **Permission errors:** `403 Forbidden`. Access will not be granted on the
  next attempt.
- **Not found:** `404 Not Found`, when the resource is confirmed not to exist.
- **Programming errors:** `TypeError`, `AttributeError`, `KeyError` — these
  usually indicate a bug in the code.

```python
# Do not retry validation or auth errors.
policy = RetryPolicy().on(TimeoutError, ConnectionError)
# Not: .on(Exception) or .on(HTTPError)
```

---

## Operations that are too long

`max_time()` controls when Relinker will allow another retry attempt. It is not
a hard timeout for user code that is already running.

If the wrapped function blocks for 10 minutes, `max_time(30)` does not
interrupt it. The check only happens between attempts, before sleeping.

```python
# This does NOT cancel a slow function mid-execution.
policy = RetryPolicy().on(TimeoutError).max_time(30)
```

If you need a hard timeout for individual calls, use the mechanism provided by
the underlying library (e.g., `requests` timeout parameter, `asyncio.wait_for`,
or a thread with a join timeout).

---

## Retry storms

When many clients fail at the same time and retry without delay or coordination,
the downstream service receives a large spike in traffic exactly when it is most
vulnerable. This makes recovery harder.

Signs you may be in this situation:

- many tasks sharing the same downstream service;
- no jitter on the delay;
- no `RetryBudget`;
- many attempts per task.

See [Common mistakes](common-mistakes.md) and [Choosing a policy](choosing-a-policy.md)
for safer configurations.

---

## Without observability

If retries succeed silently after multiple failures, the team may never know
that a dependency is intermittently unhealthy.

At a minimum, log retries:

```python
import logging
policy = RetryPolicy().attempts(5).on(TimeoutError).with_logging(level=logging.WARNING)
```

Or use events for structured reporting:

```python
def on_retry(event):
    logger.warning("retry attempt=%d delay=%.2f", event.attempt_number, event.delay)

policy = RetryPolicy().attempts(5).on(TimeoutError).on_retry(on_retry)
```

---

## Generators

Generator functions are not supported by Relinker. The error occurs immediately
when the generator is passed to `policy.run()`:

```python
from relinker import InvalidRetryConfigError

def my_generator():
    yield 1

try:
    policy.run(my_generator)
except InvalidRetryConfigError:
    ...  # always raised — generators are rejected
```

This is intentional. A generator yields control back to the caller; exceptions
during iteration happen outside the scope that Relinker controls and cannot be
caught and retried. Protect the individual operations that produce each item
instead. See [Troubleshooting — Generator was rejected](troubleshooting.md).

---

## Async event handlers

Event handlers must be synchronous. Async (coroutine) handlers are rejected
at registration:

```python
async def async_handler(event):
    await record(event)

# Raises InvalidRetryConfigError.
policy = RetryPolicy().on_retry(async_handler)
```

Use a synchronous handler that queues work externally. See
[Troubleshooting — async handler was rejected](troubleshooting.md).

---

## Related pages

- [Common mistakes](common-mistakes.md) — patterns and safer alternatives
- [Troubleshooting](troubleshooting.md) — symptom-by-symptom guidance
- [Safety](safety.md) — built-in guidance and warning codes
- [HTTP retry](http.md) — idempotency considerations for HTTP methods
