# 003 — Shared retry runtime bookkeeping

## Context

Executors and context managers need identical bookkeeping for attempt history,
aggregate counters, `RetryState`, and `RetryResult`.

## Decision

`RetryRuntime` centralizes attempt history, counters, state construction, and
result construction. It does not decide retry, calculate delays, sleep, or merge
sync and async control flow.

## Consequences

Shared bookkeeping is easier to keep consistent while sync and async loops remain
explicit. Runtime changes should stay limited to deterministic state and result
work.

## Alternatives considered

- Build a universal executor.
- Keep full duplication in each execution shape.
- Use complex inheritance to share loop behavior.
