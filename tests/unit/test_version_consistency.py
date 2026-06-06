"""Version consistency checks (Correction 10)."""

from __future__ import annotations

import re
from pathlib import Path


def test_pyproject_version_matches_package_version() -> None:
    """pyproject.toml version must equal relinker.__version__."""
    import relinker

    root = Path(__file__).parent.parent.parent
    content = (root / "pyproject.toml").read_text()
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    assert match is not None, "Could not find version field in pyproject.toml"
    pyproject_version = match.group(1)
    assert pyproject_version == relinker.__version__, (
        f"pyproject.toml version {pyproject_version!r} != "
        f"relinker.__version__ {relinker.__version__!r}"
    )
