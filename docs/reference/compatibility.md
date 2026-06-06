# Compatibility policy

This document defines the compatibility promises for Relinker starting from
version `1.0.0`.

## Supported Python versions

The package metadata and CI matrix define official support. The current declared
range is Python 3.10 through Python 3.13.

A newer interpreter may work locally before it becomes officially supported.
Official support is added only after it is included in CI and package classifiers.

## Version source of truth

The release version is stored in:

- `pyproject.toml` under `project.version`;
- `relinker.__version__`.

Tests require these values to match. The README intentionally does not duplicate
a current version number. Release history belongs in `CHANGELOG.md`.

## Semantic versioning

From `1.0.0`, Relinker follows semantic versioning:

- **Patch** releases contain compatible bug fixes only. No public API additions
  or removals.
- **Minor** releases may add new compatible functionality and introduce
  deprecations. Deprecated items are announced in documentation and
  `CHANGELOG.md`.
- **Major** releases contain incompatible changes, including removals of
  previously deprecated items.
- Critical security or correctness issues may require faster action. Any
  exception to the normal schedule must be documented with a migration path.

## API tiers

Relinker separates supported API into explicit tiers.

### Root API

The stable root import surface is the exact ordered list in `relinker.__all__`.
Users should prefer:

```python
from relinker import RetryPolicy, RetryBudget, retry
```

The snapshot of `relinker.__all__` is deliberate. The order of entries is
protected by an automated snapshot, but application code should not depend on
position in the list for any runtime logic. Incompatible changes to this list
require documentation, `CHANGELOG.md` notes, migration guidance, and an
updated public API contract.

`relinker.__version__` is package metadata and remains available directly. It is
not part of the star-import API because it is not listed in `relinker.__all__`.

### Documented module APIs

Module-level APIs are supported only when they meet all of these requirements:

- the module defines an explicit `__all__`;
- the module appears in the reference documentation;
- the module has a contract test for that public surface.

The current documented module API is `relinker.context.__all__`.

### Internal API

Modules under `relinker.internal` are implementation details. Their names,
functions, and data structures may change without deprecation.

Underscore-prefixed objects, including retry-budget reservation details, are also
internal even when they live near public code.

Examples of internal implementation details include `relinker.context._shared`
and `relinker.internal.runtime`.

## Behavioral compatibility

Compatibility includes more than import names. Relinker treats these as public
behavior:

- retry and stop decisions;
- exhaustion precedence;
- event names and order;
- `RetryResult` aggregate meanings;
- parity between sync, async, decorated, and context-manager execution;
- the rule that an original call does not consume retry-budget capacity;
- the distinction between a function returning `None` and a context-manager
  block that completed without calling `set_result()`;
- async cancellation signals propagate out of the retry loop;
- `max_time()` controls the retry loop between attempts and does not interrupt
  a user function that is already running.

The contract suite in `tests/contracts/` protects these semantics during internal
refactoring.

## Deprecation policy

### Historical note

Before `1.0`, incompatible changes were possible but required documentation,
migration guidance, and updated snapshots. That phase is closed.

### Active policy (from 1.0.0)

1. Deprecation is announced in a minor release via documentation and
   `CHANGELOG.md`.
2. When appropriate, a runtime warning is emitted for deprecated usage.
3. A deprecated item remains available for at least one full minor release after
   the deprecation announcement.
4. Removal happens only in a subsequent major release.
5. Critical security or correctness exceptions must include justification and a
   migration path in the release notes.

## Scope limitations

`RetryBudget` is process-local and in-memory. It does not coordinate multiple
processes or machines. This is a documented scope boundary, not an implicit
distributed guarantee.

`max_time()` controls the retry loop between attempts; it does not interrupt a
user function that is already running.

Relinker is not a circuit breaker, scheduler, task queue, or distributed rate
limiter. These are explicit non-goals, not gaps to be filled by future releases
without a separate major decision.
