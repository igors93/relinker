# Diagnostics and Guidance

Relinker is built around guidance. It does not block application-level decisions, but it helps users detect surprising or risky policies.

## Warnings

```python
from relinker import RetryPolicy

policy = RetryPolicy().forever().on(Exception).no_delay()

for warning in policy.warnings():
    print(warning.code, warning.message)
```

Warnings are advisory and non-blocking.

## Doctor

`doctor()` returns a `PolicyHealthReport`.

```python
report = policy.doctor()

print(report.risk_level)
print(report.describe())
```

Risk levels:

- `ok`: no warnings
- `warning`: something deserves review
- `risky`: the policy may cause serious operational problems

## Explain

`explain()` describes what the policy does in human language.

```python
print(policy.explain())
```

This is useful in:

- code reviews
- debugging sessions
- documentation
- production readiness checks

## Preview

`preview()` shows an estimated timeline without running user code.

```python
print(policy.preview(attempts=5))
```

It can also include a worst-case load estimate:

```python
print(policy.preview(attempts=5, concurrent_executions=1000))
```

For structured data, use `estimate_load()`:

```python
estimate = policy.estimate_load(concurrent_executions=1000)

print(estimate.maximum_total_calls)
print(estimate.describe())
```

The estimate is deliberately a worst case. It does not predict real traffic and
does not subtract Retry Budget capacity from the total; a budget limits retry
rate, not necessarily total operation duration.

For composed stop strategies, estimates use only safe attempt-count facts.
`ALL` compositions that include `forever()` are reported as unbounded.

## Timeline and simulation

Use `simulate()` when you want structured data:

```python
simulation = policy.simulate(attempts=5)

print(simulation.to_dict())
print(simulation.describe())
```

Use `timeline()` when you want the readable simulation report directly:

```python
print(policy.timeline(attempts=5))
```

## Common warnings

| Warning | Meaning |
|---|---|
| `forever` | The policy can retry forever |
| `no_delay` | The policy has no sleep between attempts |
| `tight_loop_risk` | The policy can retry forever without sleeping |
| `broad_exception` | The policy retries all `Exception` subclasses |
| `many_attempts` | The policy uses many attempts |
| `high_total_sleep` | The simulated sleep time is high |
| `result_retry_without_observation` | Result-based retry may exhaust silently |
| `missing_jitter` | Many deterministic delayed attempts may synchronize under concurrency |
| `missing_retry_budget` | Many attempts or infinite retry may multiply load without a budget |
| `silent_fallback` | A fallback may hide repeated failures without a give-up observer |
| `infinite_retry_with_budget` | A Retry Budget controls rate, not total duration |
| `for_testing_with_max_time` | `for_testing()` does not advance time for `max_time()` |

## Structured policy view

Use `to_dict()` when you want a safe, structured description of policy
configuration:

```python
policy = RetryPolicy().named("payments-api").attempts(5)

print(policy.to_dict())
```

The dictionary describes configuration only. It does not include runtime
reservations, locks, arguments, return values, or a way to rebuild the policy.
It reports exception exhaustion separately from result exhaustion and includes
the configured history limit. Future minor versions may add keys.

## Production recommendation

Before deploying a retry policy, run:

```python
print(policy.explain())
print(policy.preview(attempts=5))
print(policy.doctor().describe())
```
