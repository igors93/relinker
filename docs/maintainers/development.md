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
python -m pytest
python -m build
```

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

The workflow has three jobs:

1. `quality`: formatting, linting, and type checks.
2. `tests`: test matrix on Python 3.10, 3.11, and 3.12.
3. `build`: package build validation.
