# Release process

This document describes how to verify and build Relinker locally.

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
- confirm compatibility and migration guidance for incompatible changes.

## Prepare a pre-1.0 release

Preparation and publication happen in separate commits.

### Commit de preparação

- update `Unreleased`;
- validate the public API;
- validate the installed wheel;
- run the full suite;
- do not change the version.

### Commit de release

Only after everything is green:

- update `pyproject.toml`;
- update `src/relinker/__init__.py`;
- move `Unreleased` items to `## 0.9.0 - YYYY-MM-DD`;
- create a new empty `Unreleased`;
- run the pipeline again;
- create the tag only after CI is green.

Checklist for `0.9.0`:

- changelog preparado
- API snapshot revisado
- typing examples passam
- wheel validator passa
- stability matrix revisada
- 1.0 readiness permanece honesta

Do not mark external-validation items complete based only on CI.

## Version bump

Update the version in two places:

- `src/relinker/__init__.py` — `__version__`
- `pyproject.toml` — `[project] version`

## CHANGELOG

Add an entry to `CHANGELOG.md` with the new version, date, and a summary of changes. Move everything under `## Unreleased` to the new versioned section.

## Build

```bash
python -m build
```

This produces:
- `dist/relinker-X.Y.Z.tar.gz` — source distribution
- `dist/relinker-X.Y.Z-py3-none-any.whl` — wheel

## Verify the build

```bash
pip install dist/relinker-X.Y.Z-py3-none-any.whl
python scripts/validate_installed_wheel.py
```

## Publish to PyPI

Push the tag and the GitHub Actions workflow handles publishing via Trusted Publishing:

```bash
git tag v0.X.Y
git push origin v0.X.Y
```

After publishing, verify the release:

```bash
pip install relinker==0.X.Y
python -c "import relinker; print(relinker.__version__)"
```
