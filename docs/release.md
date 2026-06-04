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
python -m mypy src

# Tests
python -m pytest

# Build
python -m build
```

All steps must pass with no errors before a release.

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
python -c "import relinker; print(relinker.__version__)"
```

## Publish to PyPI

Once the package is published on PyPI, the install command will be:

```bash
pip install relinker
```

Until then, install from GitHub:

```bash
pip install git+https://github.com/igors93/relinker.git
```
