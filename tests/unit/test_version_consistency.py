"""Version consistency checks (Correction 10)."""

from __future__ import annotations

from pathlib import Path

import tomllib


def test_pyproject_version_matches_package_version() -> None:
    """pyproject.toml version must equal relinker.__version__."""
    import relinker

    root = Path(__file__).parent.parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text())
    pyproject_version = data["project"]["version"]
    assert pyproject_version == relinker.__version__, (
        f"pyproject.toml version {pyproject_version!r} != "
        f"relinker.__version__ {relinker.__version__!r}"
    )
