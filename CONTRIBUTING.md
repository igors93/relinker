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
python -m pytest
python -m build
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
