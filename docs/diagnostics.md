# Diagnostics

Diagnostics help users understand retry behavior before production.

RetryFlow does not block risky application-level decisions. Instead, it gives advisory tools.

## Warnings

```python
from retryflow import RetryPolicy

policy = RetryPolicy().forever().on(Exception).no_delay()

for warning in policy.warnings():
    print(warning.code)
    print(warning.message)
    print(warning.hint)
```

Warnings are non-blocking. They are useful in tests, reviews, CLI tools, or startup checks.

### Warning codes

| Code | When it fires |
|------|---------------|
| `forever` | Policy can retry forever (no attempt or time limit) |
| `no_delay` | Policy has no delay between attempts |
| `broad_exception` | Policy retries all `Exception` subclasses |
| `many_attempts` | Policy uses more than 10 attempts |
| `high_total_sleep` | Simulated total sleep exceeds 300 seconds |
| `return_result_precedence` | `return_result()` is set alongside a fallback or exception factory |
| `result_retry_without_observation` | Result-based retry is configured with no way to observe exhaustion |
| `background_broad_exception` | Broad exception combined with many attempts or forever retry |

### Example: checking warnings at startup

```python
policy = (
    RetryPolicy()
    .attempts(10)
    .on(Exception)
    .exponential_delay(base=0.5, maximum=30)
)

warnings = policy.warnings()
if warnings:
    for w in warnings:
        print(f"[{w.code}] {w.message}")
        if w.hint:
            print(f"  Hint: {w.hint}")
```

## Simulation

Simulation estimates the delay timeline without calling user code:

```python
policy = RetryPolicy().exponential_delay(base=1, maximum=30)

simulation = policy.simulate(attempts=5)

print(simulation.attempt_count)
print(simulation.total_sleep)
print(simulation.max_delay)
print(simulation.stops_early)
print(simulation.describe())
```

### Simulated attempt fields

Each `RetrySimulationAttempt` contains:

| Field | Description |
|-------|-------------|
| `attempt_number` | One-based attempt number |
| `delay_before_next_attempt` | Delay before the next attempt |
| `cumulative_sleep` | Total sleep accumulated up to this attempt |
| `stops_after_attempt` | Whether the stop strategy fires here |

### Serialisation

```python
sim = policy.simulate(attempts=5)

# As a dict
d = sim.to_dict()

# As JSON
print(sim.to_json(indent=2))
```

## Timeline alias

`timeline()` is a readable shortcut over `simulate().describe()`:

```python
print(policy.timeline(attempts=5))
```

## Policy explanation

`explain()` returns a human-readable summary of the policy plus any warnings:

```python
print(policy.explain())
```

## Why diagnostics matter

Retry can make a system safer, but it can also make incidents worse if a policy is too aggressive. Diagnostics help users understand behavior without forcing rules on them.
