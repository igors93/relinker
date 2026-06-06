# 002 — Mutually exclusive exhaustion behavior

## Context

Retry exhaustion can return the last result, raise the last exception, use a
fallback, or raise a custom exception. Allowing several of those states at once
made precedence hard to reason about.

## Decision

The last exhaustion configuration wins. A central helper resets the related
fields together, contradictory construction is rejected, and the old precedence
warning was removed once invalid states became impossible.

## Consequences

Policy state is easier to inspect and executors do not need to resolve
conflicting flags. Tests assert the intended last-configuration-wins behavior.

## Alternatives considered

- Keep conflicting flags and define precedence in the executor.
- Emit warnings without preventing invalid state.
- Introduce a new public exhaustion-configuration object.
