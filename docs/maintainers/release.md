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
python - <<'PY'
import relinker

for name in relinker.__all__:
    getattr(relinker, name)

assert isinstance(relinker.__version__, str)
assert relinker.__version__

print(
    f"Import OK: {len(relinker.__all__)} public exports, "
    f"version {relinker.__version__}"
)
PY
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
