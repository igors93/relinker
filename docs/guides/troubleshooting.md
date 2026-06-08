# Troubleshooting

Organized by symptom. Each section explains what to check and why.

---

## "The function did not retry"

**1. The exception type is not configured.**

Relinker only retries exceptions that match the configured condition. Any other
exception propagates immediately.

```python
# Only retries TimeoutError — ConnectionError propagates without retrying.
policy = RetryPolicy().attempts(3).on(TimeoutError)
```

Check: does the exception your code raises match what `.on(...)` expects?

Use `isinstance(error, TimeoutError)` in a test or add a temporary
`on_failure` handler to print `type(event.state.last_error)`.

**2. The policy has only one attempt.**

`RetryPolicy()` with no stop strategy allows one attempt by default. A single
attempt means there is nothing to retry.

```python
# Only attempts once — never retries.
RetryPolicy().on(TimeoutError).run(call)
```

Add `.attempts(n)` or `.max_time(seconds)`.

**3. The policy already exhausted at a previous call.**

Each `policy.run(...)` call is independent. The policy object is immutable.
Exhaustion from one call does not carry over to another.

**4. The function is a generator.**

Generator functions are rejected at registration time:

```python
from relinker import InvalidRetryConfigError

def my_gen():
    yield 1

try:
    policy.run(my_gen)
except InvalidRetryConfigError:
    ...  # generator functions are not supported
```

This is intentional: exceptions during iteration happen outside the call that
Relinker controls and cannot be retried safely. Protect the call that produces
each item instead:

```python
def fetch_item(item_id: int) -> dict:
    return db.get(item_id)

fetch_with_retry = RetryPolicy().attempts(3).on(ConnectionError).run
items = [fetch_with_retry(fetch_item, item_id) for item_id in ids]
```

**5. `TryAgain` is not being raised.**

`TryAgain` bypasses the normal exception filter. If the function does not raise
`TryAgain` (or the configured exception), Relinker treats the outcome as
final — including a returned `None`.

**6. The result condition never triggers.**

With `retry_if_result`, the function return value must match the predicate. A
returned `None` is a real value and matches only if the predicate returns `True`
for it.

---

## "The function retried more times than I expected"

**1. Attempts counts total calls, not retries.**

`attempts(5)` allows up to 5 total calls: the original plus 4 retries. The
first call is not a retry and is not counted against the retry budget.

```python
# Calls: attempt 1 (original) + attempt 2 + ... + attempt 5 = 5 total.
RetryPolicy().attempts(5)
```

**2. Composed stop strategies.**

`AND` compositions require both conditions to allow stopping:

```python
# Stops when BOTH: more than 3 attempts AND more than 30 seconds elapsed.
RetryPolicy().attempts(3).and_stop_after_time(30)
```

`OR` compositions stop when either condition triggers:

```python
# Stops when attempts > 3 OR elapsed > 30 seconds.
RetryPolicy().attempts(3).or_stop_after_time(30)
```

Verify which composition you are using.

**3. `RetryBudget` only limits additional attempts.**

The original call is not counted against budget capacity. The budget controls
how many retries (additional attempts) may be scheduled during a rolling period.
It does not limit total calls.

Use `budget.snapshot(key)` to inspect current capacity:

```python
snap = budget.snapshot("my-key")
print(snap.active, snap.available_now)
```

---

## "My program became slow"

**1. Check the simulated total sleep.**

Before running real code, estimate total delay with `simulate()`:

```python
sim = policy.simulate(attempts=5)
print(f"Total simulated sleep: {sim.total_sleep:.1f}s")
print(sim.describe())
```

Use `timeline()` for a human-readable view:

```python
print(policy.timeline(attempts=5))
```

**2. Check the delay configuration.**

Exponential backoff grows quickly. With `base=2` and 5 retries, the delays can
reach 2, 4, 8, 16, 32 seconds before `maximum` caps them.

Reduce `base`, lower `maximum`, or use fewer attempts.

**3. `Retry-After` from the server.**

When using `retry_after_delay`, the server controls the delay. Large
`Retry-After` values will be respected up to the configured `maximum`.

```python
from relinker import parse_retry_after

seconds = parse_retry_after(response.headers.get("Retry-After", ""), default=1.0)
print(f"Server asked us to wait {seconds}s")
```

**4. `max_time()` is not a hard timeout.**

`max_time(seconds)` limits when a new retry is allowed — it does not interrupt
a running call. If the wrapped function blocks for 5 minutes, `max_time(30)`
does not cancel it.

If the total program time surprises you, check whether the wrapped function
itself is slow rather than the retry delay.

**5. `RetryBudget` queue delay.**

When shared budget capacity is exhausted, retries are queued until a slot opens
in the rolling window. This can add waiting time beyond the normal policy delay.

Inspect with `budget.snapshot(key).next_available_in`.

---

## "Many calls happened at the same time"

**1. No jitter configured.**

Without jitter, all retrying clients wait exactly the same duration and fire
again at the same instant. This is called a thundering herd or retry storm.

```python
# All clients retry at t=1, t=2, t=4, t=8 — synchronized.
RetryPolicy().attempts(5).exponential_delay(base=1, maximum=30)

# Better: different clients wake at different times.
RetryPolicy().attempts(5).exponential_delay(base=1, maximum=30).jitter(maximum=0.5)
```

**2. Many concurrent executions without a `RetryBudget`.**

Without a shared budget, every concurrent execution retries independently.
With 1000 tasks and 5 attempts each, a failure could produce up to 5000 calls.

```python
budget = RetryBudget(max_retries=50, per=60)

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
    .with_retry_budget(budget, key="shared-api")
)
```

`RetryBudget` is process-local. It does not coordinate between separate
processes or machines.

**3. Estimate worst-case load before deploying.**

```python
estimate = policy.estimate_load(concurrent_executions=1000)
print(estimate.describe())
```

The estimate is a worst case and does not subtract budget-limited retries from
the total.

---

## "The final error is not what I expected"

**1. `TryAgain` wraps the original cause.**

When application code raises `TryAgain(cause=original_error)`, Relinker
preserves `original_error` throughout retry history. The final exception after
exhaustion reflects this preserved cause.

If you raise `TryAgain` without an explicit cause, the most recent context is
used. If `TryAgain` is raised bare (without `raise TryAgain(...) from error`),
the history will record it as a plain retry signal.

```python
raise TryAgain("not ready yet")            # cause: None
raise TryAgain("not ready") from original  # cause: original
```

See [TryAgain reference](../reference/try-again.md) for the full contract.

**2. Exhaustion behavior is the last configured.**

Methods like `raise_last()`, `fallback_value()`, and `on_exhausted_raise()` are
mutually exclusive. The last one called wins:

```python
# Final behavior: re-raise the original (fallback_value is overridden).
policy = RetryPolicy().fallback_value("safe").raise_last()
```

See [Exhaustion behavior](../concepts/exhaustion.md) for the precedence table.

**3. Non-retryable exceptions are not exhaustion.**

An exception that does not match the retry condition is propagated immediately.
No fallback is applied, and `after_giveup` does not fire.

**4. Use `return_result()` to inspect what happened.**

```python
result = policy.return_result().run(operation)

print(result.succeeded, result.exhausted)
print(result.attempt_count, result.failed_attempts)
for attempt in result.history:
    print(attempt.error_type, attempt.error_message)
```

Use `result.story()` for a readable execution narrative.

---

## "My async event handler was rejected"

Event handlers in Relinker must be synchronous. Async handlers (coroutine
functions) are rejected when the policy is registered:

```python
async def on_retry(event):
    await send_metric(event)

# Raises InvalidRetryConfigError — async handlers are not supported.
policy = RetryPolicy().on_retry(on_retry)
```

**Why:** an async handler could only be awaited from an async execution path,
but Relinker supports both sync and async execution. Blocking on an async
handler in a sync path would require running a new event loop, which is
incompatible with environments that already have a loop.

**Alternative:** use a synchronous handler that schedules work externally:

```python
import queue

_events: queue.Queue = queue.Queue()

def on_retry(event) -> None:
    _events.put_nowait({"attempt": event.attempt_number, "delay": event.delay})

policy = RetryPolicy().attempts(3).on_retry(on_retry)
```

Process `_events` from a background thread or async task in your application.

Avoid slow operations in handlers. A handler runs inline before sleep; a slow
handler adds latency to every retry.

---

## "Generator was rejected"

This error fires when a generator function is passed to `policy.run()` or used
as a decorator target:

```python
def my_gen():
    yield 1

# Raises InvalidRetryConfigError.
policy.run(my_gen)
```

**Why:** a generator yields control to the caller. Exceptions that happen during
iteration occur outside the scope of the call that Relinker can catch and retry.

**Pattern:** protect the operation that produces each item, not the generator
itself:

```python
from relinker import RetryPolicy

fetch = RetryPolicy().attempts(3).on(ConnectionError).no_delay().run

for item_id in pending_ids:
    item = fetch(api.get_item, item_id)   # each call is protected individually
    process(item)
```

---

## Finding more information

- [Retry lifecycle](../concepts/retry-lifecycle.md) — step-by-step execution model
- [Exhaustion behavior](../concepts/exhaustion.md) — what happens when retries run out
- [Retry budgets](../concepts/retry-budgets.md) — shared capacity explained
- [Diagnostics](diagnostics.md) — `warnings()`, `doctor()`, `simulate()`, `preview()`
- [Safety](safety.md) — built-in guidance and warning codes
