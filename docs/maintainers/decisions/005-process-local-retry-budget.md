# 005 — Process-local retry budgets

## Context

Retry Budget protects a process from creating too many additional attempts during
an incident, without adding runtime dependencies.

## Decision

The budget is in-memory and process-local. Sharing requires the same
`RetryBudget` object and key. Only retries consume capacity, and unused
reservations are released when a wait is not used.

It is not a distributed rate limiter.

## Consequences

The feature stays dependency-free and predictable in one process. Cross-process
coordination requires an external integration outside this API.

## Alternatives considered

- Require Redis.
- Add a pluggable backend immediately.
- Count the original call against the budget.
- Make fail-fast the default behavior.
