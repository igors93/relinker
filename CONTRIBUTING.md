# Contributing

Thank you for considering contributing to Relinker.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Run checks

Run the same checks used by GitHub Actions:

```bash
./scripts/ci.sh
```

Or run them separately:

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest --cov=relinker --cov-report=term-missing --cov-fail-under=85
python -m build
python -m twine check --strict dist/*
```

## Auto-format code

```bash
python -m ruff check . --fix
python -m ruff format .
```

## Code principles

- Keep modules small.
- Prefer clear names over clever names.
- Avoid hidden behavior.
- Validate impossible configurations only.
- Keep user control at the center of the API.
- Prefer explicit behavior over magic.
- Add tests for bug fixes and new behavior.

## Public API changes

The root public API is protected by
`tests/contracts/test_public_api_contract.py`. Any intentional change to
`relinker.__all__` must update that snapshot, the API reference, compatibility
documentation, and user-facing migration notes when needed.

Documented module APIs follow the same rule. Internal modules and
underscore-prefixed helpers should not be promoted accidentally.

Incompatible public API changes must include `CHANGELOG.md` notes and migration
guidance.

## Pull requests

Keep changes small and focused. Separate mechanical refactors from behavior
changes whenever possible, and check the relevant items in the pull request
template.

No pull request should lower the coverage floor to make a change pass.
