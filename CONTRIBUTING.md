# Contributing to Relinker

Thank you for taking the time to contribute. This document explains how to set
up the project, what the quality bar looks like, and how to submit a change.

---

## Where to start

- **Found a bug?** Open an issue with a minimal reproducer before writing code.
- **Have a feature idea?** Open an issue to discuss it first — this avoids
  duplicate work and helps align the change with the project's design.
- **Want to improve documentation?** Go ahead and open a PR directly. Docs live
  in `docs/`, `README.md`, and `examples/`.

---

## Local setup

```bash
git clone https://github.com/igors93/relinker.git
cd relinker
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

---

## Run the checks

Run everything in one step:

```bash
./scripts/ci.sh
```

Or individually:

```bash
python -m ruff format --check .      # formatting
python -m ruff check .               # linting
python -m mypy src tests/typing      # type checks
python -m pytest --cov=relinker --cov-report=term-missing --cov-fail-under=85
python -m build
python -m twine check --strict dist/*
```

Auto-format before committing:

```bash
python -m ruff check . --fix
python -m ruff format .
```

---

## Pull requests

- **One concern per PR.** Separate behaviour changes from refactors.
- **Every bug fix needs a regression test.** Coverage must not decrease.
- **New features need documentation.** Update `docs/`, `CHANGELOG.md`, and the
  API reference when adding to the public surface.
- **Keep the PR small.** A focused change is easier to review and merge.

---

## Code principles

- Keep modules small and focused.
- Prefer clear names over clever ones.
- Avoid hidden behaviour — make the library inspectable.
- Validate impossible configurations at construction time, not silently at
  runtime.
- Keep user control at the centre of the API.

---

## Public API changes

The root public API is protected by a snapshot test in
`tests/contracts/test_public_api_contract.py`. Any intentional change to
`relinker.__all__` must:

1. Update the snapshot.
2. Update `docs/reference/api.md`.
3. Update `docs/reference/compatibility.md`.
4. Add user-facing migration notes in `docs/guides/migrating-to-1.0.md` and
   `CHANGELOG.md` when needed.

Incompatible public API changes require a major version and a prior deprecation
notice. They do not enter patch or minor releases.

---

## Stable release rules

Relinker has a stable public API from `1.0.0`. When contributing:

- Incompatible changes to public exports or behavioural contracts require a
  major version and a documented deprecation path.
- New features must not break existing contracts.
- Deprecations must be documented in `CHANGELOG.md`, the reference docs, and
  include a runtime warning where practical.
- Bug fixes must include a regression test.
- Coverage must not decrease. Do not lower the coverage floor to pass a change.
