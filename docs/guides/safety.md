# Safety

Retry is powerful, but it can make incidents worse when used without care.

Relinker does not force application-level rules. Instead, it gives tools that
help users reason about behavior.

## Use specific exceptions when possible

```python
RetryPolicy().on(TimeoutError, ConnectionError)
```

Avoid retrying every exception unless that is intentional:

```python
RetryPolicy().on(Exception)
```

Relinker will emit a `broad_exception` warning when `.on(Exception)` is used. When combined with many attempts or `forever()`, the additional `background_broad_exception` warning fires.

## Prefer backoff and jitter for external services

```python
policy = (
    RetryPolicy()
    .attempts(5)
    .exponential_delay(base=1, maximum=30)
    .jitter(maximum=0.5)
)
```

This helps avoid many clients retrying at exactly the same moment.

## Be careful with retry forever

```python
RetryPolicy().forever()
```

This can be valid for background workers, but the application should control
shutdown, cancellation, monitoring, and alerting.

A `forever` warning fires to remind you.

## Be careful with many attempts

Policies with more than 10 attempts trigger a `many_attempts` warning. High attempt counts can amplify load on downstream services during incidents.

## Be careful with non-idempotent operations

Retrying operations like payments, order creation, or email sending can duplicate side effects if the operation is not idempotent.

Use idempotency keys or application-level safeguards.

## Check total sleep time

Use `simulate()` to estimate how long a policy could sleep:

```python
sim = policy.simulate(attempts=10)
print(f"Total simulated sleep: {sim.total_sleep:.1f}s")
```

If total sleep exceeds 300 seconds, a `high_total_sleep` warning fires.

## Observe result-based retry exhaustion

When using `retry_if_result`, configure at least one of these to make exhaustion observable:

```python
policy.return_result()           # inspect RetryResult.exhausted
policy.fallback(lambda r: ...)   # provide a fallback value
policy.raise_on_result_exhausted()  # raise RetryExhaustedError
```

Without any of these, exhaustion is silent — the function returns the last value as if it succeeded. Relinker emits a `result_retry_without_observation` warning for this case.

## Use diagnostics

```python
warnings = RetryPolicy().forever().on(Exception).no_delay().warnings()
for w in warnings:
    print(f"[{w.code}] {w.message}")
```

Warnings are advisory and do not block your application. See [Diagnostics](diagnostics.md) for the full list of warning codes.
