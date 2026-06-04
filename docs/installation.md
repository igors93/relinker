# Installation

## From GitHub

RetryFlow is not yet published on PyPI. Install directly from GitHub:

```bash
pip install git+https://github.com/igors93/retryflow.git
```

To install a specific tag or branch:

```bash
pip install git+https://github.com/igors93/retryflow.git@main
pip install git+https://github.com/igors93/retryflow.git@v0.4.0
```

## From source

Clone the repository and install in editable mode:

```bash
git clone https://github.com/igors93/retryflow.git
cd retryflow
pip install -e .
```

## Future PyPI installation

Once published to PyPI, the install command will be:

```bash
pip install retryflow
```

## Requirements

- Python 3.10 or newer
- No runtime dependencies

## Verify installation

```python
import retryflow
print(retryflow.__version__)
```

## Optional: development dependencies

To run tests, linting, and type checks:

```bash
pip install -e ".[dev]"
```

Or install manually:

```bash
pip install pytest pytest-asyncio ruff mypy build
```
