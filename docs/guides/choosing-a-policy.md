# Choosing a Policy

A quick reference to help you decide what to use.

---

## Decision tree

```
Can the failure disappear on its own?
├── No  → do not use retry.
└── Yes
    ├── Can the operation be repeated safely?
    │   ├── No  → add idempotency safeguards first.
    │   │         See: When not to retry — idempotency.
    │   └── Yes
    │       ├── Do many concurrent executions share the same downstream service?
    │       │   ├── Yes → consider RetryBudget.
    │       │   └── No  → a local policy is usually enough.
    │       ├── Does the service return Retry-After?
    │       │   ├── Yes → respect that value with retry_after_delay().
    │       │   └── No  → use exponential backoff with jitter.
    │       └── Always set an attempt limit or a time limit.
```

---

## Table by situation

| Situation | Recommended approach | Why |
|---|---|---|
| Temporary exception | `.on(SpecificError)` | Only retries errors that can resolve |
| Temporary result (not an exception) | `.retry_if_result(predicate)` | Not all failures raise exceptions |
| Unstable external service | `.exponential_delay(base=1, maximum=30)` | Reduces pressure during degradation |
| Many concurrent clients | `.jitter(maximum=0.5)` | Prevents synchronized retry bursts |
| Many tasks in the same process | `.with_retry_budget(budget, key=...)` | Limits shared retry rate |
| API with rate limiting | `retry_after_delay(default=1.0, maximum=60.0)` | Respects the server's guidance |
| Poll until state changes | `TryAgain` or `retry_if_result` | Explicit retry signal |
| Need full visibility | `.return_result()` | Exposes attempts, timing, errors |
| Check policy before shipping | `policy.doctor()` | Reports known risk patterns |
| Test without sleeping | `.for_testing()` | Replaces sleep with no-op |

---

## Starting policies for common cases

### External API

Use exponential backoff and jitter. Limit exceptions. Set a cap.

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

### Rate-limited API

Respect the server's requested delay when present.

```python
from relinker import RetryPolicy, retry_after_delay, retry_if_status

policy = (
    RetryPolicy()
    .attempts(5)
    .retry_if_result(retry_if_status({429, 500, 502, 503, 504}))
    .stateful_delay(retry_after_delay(default=1.0, maximum=60.0))
)
```

### Database transient failure

Short delays. Specific exceptions. Modest attempt count.

```python
policy = (
    RetryPolicy()
    .attempts(4)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=0.1, factor=2, maximum=2)
    .jitter(maximum=0.2)
)
```

### Background job (long-running)

More attempts, larger delays, `RetryBudget` for shared services.

```python
from relinker import RetryBudget, RetryPolicy

budget = RetryBudget(max_retries=10, per=60)

policy = (
    RetryPolicy()
    .attempts(10)
    .on(TimeoutError, ConnectionError)
    .exponential_delay(base=2, maximum=120)
    .jitter(maximum=1.0)
    .with_retry_budget(budget, key="background-service")
)
```

### Polling

Poll until a value changes; retry on expected non-final states.

```python
from relinker import RetryPolicy, TryAgain

policy = RetryPolicy().attempts(20).fixed_delay(2)

def wait_for_job(job_id: str) -> str:
    status = service.get_status(job_id)
    if status == "pending":
        raise TryAgain(f"job {job_id!r} is still pending")
    return status
```

---

## Safety check before deploying

Run these three commands on every policy before it reaches production:

```python
print(policy.explain())          # plain-language description
print(policy.preview(attempts=5))  # estimated timing
print(policy.doctor().describe())  # known risks
```

If `risk_level` is `risky`, review the policy.

See also: [Production checklist](production-checklist.md).

---

## Related pages

- [Policy builder](policy-builder.md) — full method reference
- [Retry budgets](../concepts/retry-budgets.md) — shared capacity explained
- [When not to retry](when-not-to-retry.md) — situations where retry is unsafe
- [Common mistakes](common-mistakes.md) — patterns to avoid
