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

Each warning has a severity that reflects its operational impact:

- `advisory` — guidance for production readiness or predictability
- `warning` — configuration that deserves operational review
- `critical` — high risk of serious operational harm when the configuration is reachable

| Warning | Severity | Meaning |
|---|---|---|
| `implicit_default_policy` | advisory | The policy still uses all implicit retry defaults: broad `Exception`, 3 attempts, and no delay |
| `high_total_sleep` | advisory | The simulated sleep time is high |
| `missing_jitter` | advisory | Many deterministic delayed attempts may synchronize under concurrency |
| `seeded_random_delay` | advisory | A fixed seed repeats the same per-attempt random delays across executions that reuse it |
| `for_testing_with_max_time` | advisory | `for_testing()` does not advance time for `max_time()` |
| `forever` | warning | The policy can retry forever |
| `no_delay` | warning | The policy has no sleep between attempts |
| `broad_exception` | warning | The policy retries all `Exception` subclasses |
| `broad_os_error` | warning | The policy explicitly retries `OSError`, which can include non-transport operating-system failures |
| `many_attempts` | warning | The policy uses many attempts |
| `result_retry_without_observation` | warning | Result-based retry may exhaust silently |
| `missing_retry_budget` | warning | Many attempts or infinite retry may multiply load without a budget |
| `silent_fallback` | warning | A fallback may hide repeated failures without a give-up observer |
| `infinite_retry_with_budget` | warning | A Retry Budget controls rate, not total duration |
| `tight_loop_risk` | critical | The policy can retry forever without sleeping |
| `unbounded_history` | critical | An effectively infinite policy retains every attempt record |
| `background_broad_exception` | critical | Broad exception handling is combined with many attempts or forever retry |

`background_broad_exception` is raised when `broad_exception` is paired with
many attempts or indefinite retry. Background jobs that catch all exceptions can
silently mask bugs and amplify load on a degraded service. The warning is
non-blocking. To reduce the risk: narrow the exception types, limit attempts or
add `max_time()`, configure a Retry Budget, or add a give-up observer. A circuit
breaker external to the library is appropriate when the operation must shed load
independently of the retry count.

Warnings about retry behaviour are omitted when the stop strategy guarantees
that no retry can occur, such as `max_time(0)` or `attempts(1)`.

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
