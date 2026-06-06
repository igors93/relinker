# Development

This document explains how to work on Relinker locally and run the same checks
used by GitHub Actions.

## Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Install development dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run all checks locally

```bash
./scripts/ci.sh
```

Or run each command manually:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest --cov=relinker --cov-report=term-missing --cov-fail-under=85
python -m build
python -m twine check --strict dist/*
```

`./scripts/ci.sh` runs the same sequence.

## Auto-format code

```bash
python -m ruff check . --fix
python -m ruff format .
```

## GitHub Actions

The CI workflow runs on:

- pushes to `main`
- pull requests to `main`
- manual runs through `workflow_dispatch`

The workflow has four jobs:

1. `quality`: formatting, linting, and type checks.
2. `documentation`: documentation and public API contracts.
3. `tests`: test matrix on Python 3.10, 3.11, 3.12, and 3.13 across Ubuntu
   and macOS.
4. `validate-package`: package build validation.

`quality` runs on Python 3.12. `documentation` runs the documentation tests and
the public API snapshot. `validate-package` depends on both `tests` and
`documentation`, builds the package, validates metadata with Twine, checks every
name in `relinker.__all__` from the installed wheel, and verifies the `py.typed`
marker.

## Coverage floor

Coverage must stay at or above 85%. The floor exists to prevent quiet
regressions and should not be reduced to pass an individual change.

Raise the floor only in a separate maintenance change after coverage has stayed
comfortably higher for a while.

## Branch protection

Repository settings should require the CI jobs to pass before merging to `main`.
