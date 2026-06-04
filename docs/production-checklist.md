# Production Checklist

Use this checklist before deploying retry behavior.

## Policy behavior

- [ ] Does the policy have a clear stop condition?
- [ ] Is `forever()` truly required?
- [ ] Is there a delay between attempts?
- [ ] Is jitter needed to avoid retry storms?
- [ ] Are exception types specific enough?
- [ ] Does result-based retry have clear exhaustion behavior?
- [ ] Is fallback behavior intentional?
- [ ] Is the total possible sleep acceptable?

## External services

- [ ] Could retries increase pressure on a degraded service?
- [ ] Are retry attempts safe for the operation?
- [ ] Are non-idempotent HTTP methods reviewed carefully?
- [ ] Does the API provide `Retry-After`?
- [ ] Should the policy respect rate limits?

## Observability

- [ ] Are retries logged or observable?
- [ ] Is structured logging safe by default?
- [ ] Are sensitive error messages excluded from logs?
- [ ] Are retry metrics needed?
- [ ] Does the team know how to inspect `RetryResult`?

## Testing

- [ ] Are tests avoiding real sleep?
- [ ] Are exhausted paths tested?
- [ ] Are fallback paths tested?
- [ ] Are async retry paths tested if used?

## RetryFlow checks

Run:

```python
print(policy.explain())
print(policy.preview(attempts=5))
print(policy.doctor().describe())
```

If `risk_level` is `risky`, review the policy before production.
