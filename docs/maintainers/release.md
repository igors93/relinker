# Release process

This document describes how to verify and build Relinker locally before a
release. Repository publication steps (tagging, pushing, PyPI upload) are
performed manually by the maintainer after CI is green.

## Release phases

1. Prepare release notes in `CHANGELOG.md`.
2. Review public API snapshots (`relinker.__all__` and `relinker.context.__all__`).
3. Update version sources (`pyproject.toml` and `src/relinker/__init__.py`).
4. Run the full local validation pipeline.
5. Build clean artifacts.
6. Validate the wheel in an isolated environment.
7. Review the generated diff for unexpected changes.
8. The maintainer performs repository publication actions separately after CI is
   green (tag creation, remote push, PyPI upload).

## Local checks

Run the full quality pipeline before cutting a release:

```bash
./scripts/ci.sh
```

Or run individual steps:

```bash
# Format check
python -m ruff format --check .

# Lint
python -m ruff check .

# Type check
python -m mypy src tests/typing

# Tests
python -m pytest --cov=relinker --cov-report=term-missing --cov-fail-under=85

# Build
python -m build

# Distribution metadata
python -m twine check --strict dist/*
```

All steps must pass with no errors before a release.

## Public API review

Before the version bump:

- review the diff of `relinker.__all__`;
- review the public API snapshot;
- review `relinker.context.__all__`;
- confirm that `docs/reference/api.md` corresponds to the exports;
- confirm compatibility and migration guidance for any incompatible changes.

## Version bump

Update the version in two places:

- `src/relinker/__init__.py` — `__version__`
- `pyproject.toml` — `[project] version`

## CHANGELOG

Add an entry to `CHANGELOG.md` with the new version, date, and a summary of
changes. Move everything under `## Unreleased` to the new versioned section.
Leave a new empty `## Unreleased` section at the top.

## Build

```bash
python -m build
```

This produces:
- `dist/relinker-X.Y.Z.tar.gz` — source distribution
- `dist/relinker-X.Y.Z-py3-none-any.whl` — wheel

## Verify the build

Install the wheel in an isolated virtual environment and run the validator:

```bash
python scripts/validate_installed_wheel.py
```

## Checklist for 1.1.0

- [ ] `pyproject.toml` reports `1.1.0`.
- [ ] `relinker.__version__` reports `1.1.0`.
- [ ] `CHANGELOG.md` contains a dated `1.1.0` section.
- [ ] A new empty `Unreleased` section exists.
- [ ] Public API snapshots are unchanged.
- [ ] Ruff, mypy, tests, coverage, build, and Twine pass.
- [ ] The installed wheel validator passes.
