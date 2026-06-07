# Retry budgets

A retry budget limits how many **additional attempts** a group of executions may
schedule during a rolling period. The first call is not counted.

```python
from relinker import RetryBudget, RetryPolicy

budget = RetryBudget(max_retries=20, per=60)

policy = (
    RetryPolicy()
    .attempts(5)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=1, maximum=30)
    .with_retry_budget(budget, key="payments-api")
)
```

`attempts(5)` limits one execution. `RetryBudget(max_retries=20, per=60)` limits
shared retry activity across all policies using the same budget object and key.
Different keys on the same object have independent capacity.

## Waiting behavior

The first release always waits for the next reserved slot. Relinker combines the
normal policy delay with the shared budget and sleeps once for the total delay.
The budget never shortens backoff, jitter, `Retry-After`, or a state-aware delay.

`max_time()` includes the total wait. When the wait would exceed the configured
time budget, Relinker cancels the unused reservation and follows the existing
exhaustion behavior without sleeping.

Interrupted synchronous sleeps and canceled asynchronous sleeps also release an
unused reservation before re-raising the interruption unchanged.

## Observability

The existing `before_sleep` event remains the only sleep event. Its `delay` is
the actual total wait. The event state provides:

- `policy_delay`: delay produced by the configured delay strategy;
- `budget_delay`: additional shared-budget delay;
- `next_delay`: total actual delay.

The budget key is not included in structured logs by default.

## Snapshot

`budget.snapshot(key)` returns a momentary, read-only view of one key:

```python
snapshot = budget.snapshot("payments-api")

print(snapshot.active)
print(snapshot.queued)
print(snapshot.available)
print(snapshot.available_now)
print(snapshot.next_available_in)
```

`active` counts reservations inside the current rolling window. `queued` counts
reservations scheduled strictly in the future. `available` is kept for
compatibility and means the same thing as `available_now`: how many retries could
be reserved immediately without breaking the budget. `next_available_in` is an
estimate, in seconds, based on the reservations currently known to this process.

The snapshot is process-local and can become stale immediately after it is read.
It is useful for diagnostics, not for distributed coordination.

## Scope and simulation

`RetryBudget` is in-memory and process-local. State is lost on restart and is not
shared between processes or machines.

`simulate()` continues to model normal policy delays only. `preview()` explains
that shared budget waiting depends on runtime activity and is not simulated.
