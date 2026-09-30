# Installation

## From PyPI

```bash
pip install relinker
```

## From GitHub

To track the latest development version or a specific branch:

```bash
pip install git+https://github.com/igors93/relinker.git
```

To install a specific tag or branch:

```bash
pip install git+https://github.com/igors93/relinker.git@main
pip install git+https://github.com/igors93/relinker.git@v1.3.2
```

## From source

Clone the repository and install in editable mode:

```bash
git clone https://github.com/igors93/relinker.git
cd relinker
pip install -e .
```

## Requirements

- Python 3.10 or newer
- No runtime dependencies

## Verify installation

```python
import relinker
print(relinker.__version__)
```

## Optional: development dependencies

To run tests, linting, and type checks:

```bash
pip install -e ".[dev]"
```

The `dev` extra pins the exact Ruff and mypy versions used by CI. Installing
those tools separately can produce different formatting or type-check results.
