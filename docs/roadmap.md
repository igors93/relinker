# Roadmap

RetryFlow is still evolving. This roadmap describes direction, not guaranteed deadlines.

## Documentation

- Expand examples for common production scenarios.
- Add a full PyPI-ready README.
- Add guides for migration from manual retry loops.
- Add comparison notes explaining RetryFlow's philosophy.

## API and usability

- Add more recipes for common scenarios.
- Improve context manager consistency with normal executors.
- Add more user-friendly policy inspection helpers.
- Continue improving naming clarity.

## Reliability

- Keep strict typing.
- Keep zero required runtime dependencies.
- Keep strong CI checks.
- Expand tests around edge cases and failure modes.

## Observability

- Improve structured logging documentation.
- Add examples for metrics/tracing integration without required dependencies.

## Packaging

- Publish on PyPI when documentation and release process are ready.
- Add release automation when appropriate.

## Guiding principle

Every new feature should answer yes to at least one of these questions:

- Does it make common retry usage simpler?
- Does it make advanced retry usage possible without hacks?
- Does it help users avoid risky retry behavior?
- Does it keep the codebase modular and maintainable?
