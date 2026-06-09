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
python -m mypy src tests/typing
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
3. `tests`: test matrix on Python 3.10, 3.11, 3.12, 3.13, and 3.14 across
   Ubuntu, macOS, and Windows.
4. `validate-package`: package build validation.

`quality` runs on Python 3.12. `documentation` runs the documentation tests and
the public API snapshot. `validate-package` depends on both `tests` and
`documentation`, builds the package, validates metadata with Twine, runs the
installed wheel validator, and verifies the `py.typed` marker.

### Maintaining GitHub Action pins

Remote GitHub Actions must use a full 40-character commit SHA rather than a
mutable tag. Keep the reviewed upstream version in an adjacent comment:

```yaml
uses: actions/checkout@<full-commit-sha> # v6.0.3
```

When updating an action:

1. Review the upstream release in the action's official repository.
2. Verify the selected commit belongs to that repository.
3. Replace every occurrence with the same full SHA.
4. Update the adjacent version comment.
5. Run `python -m pytest tests/maintenance/test_ci_contract.py -v`.

Dependabot is configured to propose GitHub Actions updates. Review those pull
requests rather than replacing SHA pins with tags. Every workflow job must keep
an explicit `timeout-minutes` value, and checkout steps must use
`persist-credentials: false` unless a future workflow has a reviewed need to
perform an authenticated Git write.

## Public typing examples

Public typing examples are checked with:

```bash
python -m mypy src tests/typing
```

The examples represent supported public use. They should import from `relinker`
and avoid internal modules.

## Installed wheel validation

The package validation job:

1. builds the wheel;
2. installs it;
3. runs `scripts/validate_installed_wheel.py`;
4. verifies `py.typed`.

The validator must import the installed distribution, not `src`.

## Performance smoke script

Maintainers can run a small manual performance smoke check:

```bash
python benchmarks/smoke.py --iterations 1000
```

This is not a CI gate and does not replace profiling. It is only a quick way to
notice coarse regressions.

## Coverage floor

Coverage must stay at or above 85%. The floor exists to prevent quiet
regressions and should not be reduced to pass an individual change.

Raise the floor only in a separate maintenance change after coverage has stayed
comfortably higher for a while.

## Branch protection

Repository settings should require the CI jobs to pass before merging to `main`.

## Stable API discipline

From `1.0.0`, the public API is stable and changes require care:

- Changes to `relinker.__all__` or `relinker.context.__all__` require a
  compatibility review. Update the snapshot, the API reference, and
  `CHANGELOG.md`.
- Removing or renaming a public export requires a major version increment. A
  deprecation warning in a minor release must come first.
- Deprecations must follow the policy in `docs/reference/compatibility.md`.
- Internal modules may change freely, but behavioral contracts must not regress.
  The contract suite in `tests/contracts/` is the protection boundary.
- Every bug fix must include a regression test before merging.
