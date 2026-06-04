# Relinker Documentation

**Simple by default, powerful by composition, safe by guidance.**

This documentation is organized for two audiences:

- users who want to add retry behavior quickly
- maintainers who want to understand how Relinker is designed

## Navigation

| Section | Purpose |
|---|---|
| [Getting started](getting-started.md) | Install and use Relinker in minutes |
| [Policy builder](policy-builder.md) | Learn the fluent `RetryPolicy` API |
| [Diagnostics and guidance](diagnostics.md) | Use warnings, doctor, preview, and explain |
| [HTTP retry](http.md) | Retry HTTP status codes and `Retry-After` |
| [Observability](observability.md) | Logging, structured logging, and events |
| [Results and statistics](results.md) | Inspect retry outcomes and per-function stats |
| [Context manager usage](context-manager.md) | Retry blocks without extracting functions |
| [Testing retry code](testing.md) | Avoid slow tests and real sleeping |
| [API reference](api-reference.md) | Public API overview |
| [Design principles](design-principles.md) | Project philosophy and architecture values |
| [Production checklist](production-checklist.md) | Review policies before production |
| [Roadmap](roadmap.md) | Planned direction |

## Recommended learning path

1. Read [Getting started](getting-started.md).
2. Try the examples in `examples/`.
3. Read [Policy builder](policy-builder.md).
4. Use [Diagnostics and guidance](diagnostics.md) before deploying retry policies.
5. Use [Production checklist](production-checklist.md) for real systems.
