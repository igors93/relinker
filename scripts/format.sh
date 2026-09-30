#!/usr/bin/env bash
set -euo pipefail

python -m ruff format .
python -m ruff check . --fix
