# Common Mistakes

Each section shows a risky pattern and a safer alternative.

---

## Retrying any exception

**Risky:**

```python
RetryPolicy().attempts(5).on(Exception)
```

This retries every failure, including permanent ones like `ValueError`,
`TypeError`, and `AttributeError`. A bug in your code will be retried 5 times
before the error is surfaced. Relinker emits a `broad_exception` warning for
this case.

**Better:**

```python
RetryPolicy().attempts(5).on(TimeoutError, ConnectionError)
```

Name the exceptions that can actually resolve on their own.

If you are unsure which exceptions a dependency raises, add a temporary
`on_failure` handler to log `type(event.state.last_error)` and observe before
deciding.

---

## Retrying every OSError as a transport failure

**Risky:**

```python
RetryPolicy().attempts(5).on(OSError)
```

`OSError` includes more than network failures. It can also represent local file,
permission, process, device, and resource errors. A large retried function may
repeat unrelated side effects when one of those failures occurs. Relinker emits
a `broad_os_error` warning for the exact `OSError` type.

**Better:**

```python
RetryPolicy().attempts(5).on(TimeoutError, ConnectionError)
```

Prefer the dependency's documented transient exceptions when they are available:

```python
RetryPolicy().attempts(5).on(HttpClientTimeout, HttpClientConnectionError)
```

Keep the retried function focused on the operation that can safely be repeated.
Specific subclasses of `OSError` do not trigger this warning because they may
represent a deliberate, well-defined transient failure.

---

## Infinite retry without a delay

**Risky:**

```python
RetryPolicy().forever().on(TimeoutError).no_delay()
```

This creates a tight loop: if the service is down, the code retries thousands
of times per second. Relinker emits `forever`, `no_delay`, and
`tight_loop_risk` warnings.

**Better:**

```python
RetryPolicy().forever().on(TimeoutError).exponential_delay(base=1, maximum=60)
```

Or add a time limit:

```python
RetryPolicy().max_time(300).on(TimeoutError).exponential_delay(base=1, maximum=60)
```

A `forever()` policy should always be paired with delays, cancellation support,
and monitoring.

---

## Fixed delay at scale without jitter

**Risky:**

```python
RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(2)
```

When many clients fail at the same time, all of them wait exactly 2 seconds
and retry together. This can overload a service that was just recovering. It is
called the thundering herd problem.

**Better:**

```python
RetryPolicy().attempts(5).on(TimeoutError).fixed_delay(2).jitter(maximum=0.5)
```

Jitter is a small random variation on the delay. Different clients wake at
different times, spreading the load.

Jitter matters when more than a handful of processes or goroutines may fail
together.

## Using a fixed jitter seed in production

**Risky for production spreading:**

```python
RetryPolicy().fixed_delay(2).jitter(maximum=0.5, seed=1)
```

A fixed seed is reproducible, but executions that reuse it receive the same
per-attempt jitter. This can preserve synchronization between workers. Relinker
emits `seeded_random_delay` for production policies that rely exclusively on
seeded random delays.

**Better for production:**

```python
RetryPolicy().fixed_delay(2).jitter(maximum=0.5)
```

Keep fixed seeds for tests and simulations, preferably with `for_testing()`.

---

## Many attempts without a shared budget

**Risky:**

```python
policy = RetryPolicy().attempts(10).on(TimeoutError).exponential_delay(base=1)

# 1000 tasks run this policy concurrently.
```

With 1000 tasks and 10 attempts each, a total outage could trigger up to 10,000
calls against a degraded service. This amplifies load exactly when the service
can least handle it.

**Better:**

```python
from relinker import RetryBudget, RetryPolicy

budget = RetryBudget(max_retries=50, per=60)

policy = (
    RetryPolicy()
    .attempts(10)
    .on(TimeoutError)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
    .with_retry_budget(budget, key="downstream-service")
)
```

`RetryBudget` limits how many additional attempts all tasks combined may make
per rolling time window. The initial call for each task is not counted.

`RetryBudget` is process-local. It does not coordinate between separate
processes or machines.

---

## Silent fallback

**Risky:**

```python
policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError)
    .fallback_value({"items": []})
)

# If the service is down, callers receive {"items": []} with no indication
# that anything failed.
```

A silent fallback hides failures from monitoring, logs, and on-call responders.
Users may see empty or stale results without knowing a dependency is unhealthy.
Relinker emits a `silent_fallback` warning for this case.

**Better:**

```python
from relinker import RetryPolicy
from relinker.event import RetryEvent

def on_exhausted(event: RetryEvent) -> None:
    logger.error("catalogue service exhausted after %d attempts", event.attempt_number)

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError)
    .on_giveup(on_exhausted)
    .fallback_value({"items": [], "degraded": True})
)
```

Or use `return_result()` so the caller can check `result.exhausted`:

```python
result = policy.return_result().run(fetch_catalogue)
if result.exhausted:
    record_incident("catalogue-service-exhausted")
```

---

## Retrying payment, order, or email operations

**Risky:**

```python
RetryPolicy().attempts(3).on(TimeoutError).run(charge_card, amount=99.00)
```

If `charge_card` succeeds on the server but the response times out before
reaching your code, retrying will charge the card a second time.

**What idempotency means:** an operation is *idempotent* when repeating it
produces the same final state as doing it once. Reading data is usually
idempotent. Charging a card or creating an order is not — unless the system
has been designed with safeguards.

**Safer approach:**

- Use an idempotency key so the server can detect and reject duplicate requests.
- Confirm with the server whether a previous attempt succeeded before retrying.
- Log or alert when payment retries occur so duplicate charges can be identified.

These safeguards belong in the application or payment provider, not in the
retry library. See [When not to retry](when-not-to-retry.md).

---

## Tests that sleep for real

**Risky:**

```python
policy = RetryPolicy().attempts(3).on(TimeoutError).fixed_delay(5)

def test_retries_twice():
    calls = 0
    def fail_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return "ok"
    result = policy.run(fail_once)
    assert calls == 2  # waits 5 seconds before asserting
```

**Better:**

```python
def test_retries_twice():
    calls = 0
    def fail_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise TimeoutError()
        return "ok"
    result = policy.for_testing().run(fail_once)
    assert calls == 2  # no sleep, runs instantly
```

`for_testing()` replaces sleep with a no-op and preserves all other policy
settings. Tests run in milliseconds regardless of configured delays.

Capture requested sleep durations for assertion:

```python
sleeps: list[float] = []
result = policy.with_sleep(sleeps.append).run(fail_once)
assert sleeps == [5.0]
```

---

## Related pages

- [When not to retry](when-not-to-retry.md)
- [Safety](safety.md)
- [Testing retry code](testing.md)
- [Diagnostics](diagnostics.md)
