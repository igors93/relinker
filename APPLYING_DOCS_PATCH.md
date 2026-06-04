# Applying this documentation patch

This archive focuses only on documentation and examples.

It replaces or adds:

- `README.md`
- `CHANGELOG.md`
- `docs/`
- `examples/`

It does not change Relinker runtime source code under `src/relinker/`.

## Apply

From the repository root:

```bash
unzip -o relinker_docs_examples_patch.zip -d .
```

Then run:

```bash
python -m ruff format .
python -m ruff check .
python -m mypy src
python -m pytest
```

Because this patch only changes Markdown and examples, runtime tests should not change unless an example is imported by tests.

## Suggested commit message

```bash
git add README.md CHANGELOG.md docs examples
git commit -m "Expand documentation and examples"
```
