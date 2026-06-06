#!/usr/bin/env bash
set -euo pipefail

python -m ruff format --check .
python -m ruff check .
python -m mypy src
python -m pytest --cov=relinker --cov-report=term-missing
python -m build
python -m twine check --strict dist/*
