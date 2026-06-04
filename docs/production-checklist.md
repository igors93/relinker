# Production checklist

Before deploying a retry policy to production, review these questions.

## Stop strategy

- [ ] Does the policy have a stop condition? `forever()` is only safe when the caller controls cancellation.
- [ ] Is the attempt count proportional to the expected failure rate? More than 10 attempts is unusual.
- [ ] Does the policy have a time limit that respects your SLA budget?

## Delay strategy

- [ ] Does the policy have a delay between attempts? No delay can cause a thundering herd.
- [ ] Does the policy cap the maximum delay? Uncapped exponential delay can grow very large.
- [ ] Does the policy add jitter for distributed systems? Jitter spreads retry load across time.

## Retry condition

- [ ] Is the exception type narrow enough? Retrying `Exception` can hide application bugs.
- [ ] Is the operation idempotent? Non-idempotent operations (writes, payments) need extra care.
- [ ] Does result-based retry have an observable outcome? Without `return_result()`, `fallback()`, or `raise_on_result_exhausted()`, result exhaustion is silent.

## Exhausted behaviour

- [ ] What happens when all retries are exhausted? Does the caller receive a meaningful error or fallback?
- [ ] Is the fallback value safe to use in production?
- [ ] If a custom exception is raised on exhaustion, is it handled by upstream callers?

## Observability

- [ ] Are retries logged? Use `with_logging()` or `on_event()`.
- [ ] Are retry statistics monitored? Use `retry_stats.snapshot()` on decorated functions.
- [ ] Are warnings checked at startup? Call `policy.warnings()` and log any findings.

## Simulation

Run a simulation before deploying:

```python
sim = policy.simulate(attempts=10)
print(f"Total simulated sleep: {sim.total_sleep:.1f}s")
print(f"Max delay: {sim.max_delay:.1f}s")
print(sim.describe())
```

Check that the simulated delays are acceptable for your use case.

## Quick review script

```python
from retryflow import RetryPolicy

def check_policy(policy: RetryPolicy) -> bool:
    warnings = policy.warnings()
    risky_codes = {"forever", "no_delay", "broad_exception", "high_total_sleep"}
    risky = [w for w in warnings if w.code in risky_codes]
    if risky:
        for w in risky:
            print(f"WARN [{w.code}]: {w.message}")
        return False
    return True

policy = RetryPolicy().attempts(5).on(TimeoutError).exponential_delay(base=0.5, maximum=10)
assert check_policy(policy), "Policy has risky warnings"
```
