# Contributing

Thank you for considering contributing to RetryFlow.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run checks

```bash
./scripts/format.sh
./scripts/lint.sh
./scripts/test.sh
```

## Code principles

- Keep modules small.
- Prefer clear names over clever names.
- Avoid hidden behavior.
- Validate impossible configurations only.
- Keep user control at the center of the API.
