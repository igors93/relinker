# Behavioral contract tests

This directory records Relinker's externally observable behavior before internal
refactoring work begins.

The tests intentionally exercise the public API through multiple execution
paths:

- synchronous and asynchronous `RetryPolicy.run*()` calls;
- synchronous and asynchronous decorated functions;
- synchronous and asynchronous retry-block context managers.

They protect contracts that must not change accidentally, including:

- exception and result retry decisions;
- exhaustion precedence;
- event order and state fields;
- bounded history with complete aggregate counters;
- shared Retry Budget behavior;
- parity between direct, decorated, and context-manager execution.

These tests are not a replacement for unit tests. Unit tests verify individual
components; contract tests verify the behavior users rely on while the internal
architecture evolves.
