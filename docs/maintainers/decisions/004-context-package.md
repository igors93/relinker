# 004 — Focused context-manager package

## Context

Context-manager retry support needs both sync and async control flow while
preserving existing imports from `relinker.context`.

## Decision

`relinker.context` remains the documented module path. Sync and async
implementations live in focused modules, and `_shared.py` contains only identical
state and helper behavior. There is no universal sync/async flow.

## Consequences

Imports stay stable, async behavior remains explicit, and shared code stays
limited to truly common mechanics.

## Alternatives considered

- Keep one monolithic context file.
- Use inheritance between public sync and async classes.
- Build a single adapter around awaitable callbacks.
