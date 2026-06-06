# 001 — Explicit public API snapshots

## Context

Relinker has a compact public surface, but internal refactoring can accidentally
remove an export or expose a helper that should remain private.

## Decision

`relinker.__all__` is the root public API. Documented modules with explicit
`__all__` values and contract tests may be secondary public APIs.

Modules under `relinker.internal` and underscore-prefixed modules or symbols are
internal. Public API snapshots require deliberate review when they change.

## Consequences

API changes are visible in tests and documentation. Adding a symbol to the root
package is a compatibility decision, not a convenience-only change.

## Alternatives considered

- Infer public API from every name that does not start with an underscore.
- Export every useful type in the root package.
- Avoid snapshots and rely on review only.
