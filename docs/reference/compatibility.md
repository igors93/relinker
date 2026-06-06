# Compatibility policy

This document defines the compatibility promises for Relinker while it evolves
toward a stable `1.0` release.

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

## API tiers

Relinker separates supported API into explicit tiers.

### Root API

The stable root import surface is the exact ordered list in `relinker.__all__`.
Users should prefer:

```python
from relinker import RetryPolicy, RetryBudget, retry
```

The snapshot of `relinker.__all__` is deliberate. Incompatible changes to this
list require documentation, `CHANGELOG.md` notes, migration guidance, and an
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
- the rule that an original call does not consume retry-budget capacity.

The contract suite in `tests/contracts/` protects these semantics during internal
refactoring.

## Deprecation policy

### Pre-1.0 changes

Before `1.0`, incompatible changes remain possible, but they must be deliberate:

1. explain the reason in `CHANGELOG.md`;
2. include migration guidance;
3. add or update snapshots and contract tests;
4. update the reference documentation;
5. avoid combining an incompatible change with unrelated refactoring.

Where practical, deprecation warnings should be preferred over immediate removal.

### After 1.0

After `1.0`, public APIs should normally be deprecated in a minor release and
removed only in a later major release. The recommended minimum is at least one
full minor release between deprecation and removal.

Security or critical correctness issues may require faster action, but the
exception and migration path must be documented clearly.

## Scope limitations

`RetryBudget` is process-local and in-memory. It does not coordinate multiple
processes or machines. This is a documented scope boundary, not an implicit
distributed guarantee.

`max_time()` controls the retry loop between attempts; it does not interrupt a
user function that is already running.
