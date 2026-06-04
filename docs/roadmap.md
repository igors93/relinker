# Roadmap

Relinker is still evolving. This roadmap describes direction, not guaranteed deadlines.

## Documentation

- Expand examples for common production scenarios.
- Add guides for migration from manual retry loops.
- Add comparison notes explaining Relinker's philosophy.
- Improve installation and PyPI setup documentation.

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

## Packaging and release

- Improve release automation (version bump, changelog, tag, publish).
- Add a structured changelog workflow.
- Verify and document Python 3.13+ compatibility when stable.
- Explore Trusted Publishing via GitHub Actions for streamlined PyPI releases.

## Guiding principle

Every new feature should answer yes to at least one of these questions:

- Does it make common retry usage simpler?
- Does it make advanced retry usage possible without hacks?
- Does it help users avoid risky retry behavior?
- Does it keep the codebase modular and maintainable?
