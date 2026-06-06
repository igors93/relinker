"""
Tests for the dependency-free release-version validation script.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_validator() -> ModuleType:
    """Load the release validator from the repository scripts directory."""
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "scripts" / "validate_release_version.py"
    specification = importlib.util.spec_from_file_location(
        "validate_release_version",
        script_path,
    )

    assert specification is not None
    assert specification.loader is not None

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def _write_project(root: Path, version: str) -> None:
    """Create the minimum files required by the release validator."""
    package = root / "src" / "relinker"
    package.mkdir(parents=True)

    (root / "pyproject.toml").write_text(
        (
            "[project]\n"
            'name = "relinker"\n'
            f'version = "{version}"\n'
        ),
        encoding="utf-8",
    )
    (package / "__init__.py").write_text(
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )


def test_normalize_release_tag() -> None:
    """Common Git tag forms must normalize to the package version."""
    validator = _load_validator()

    assert validator.normalize_release_tag("v0.7.0") == "0.7.0"
    assert validator.normalize_release_tag("0.7.0") == "0.7.0"
    assert validator.normalize_release_tag("refs/tags/v0.7.0") == "0.7.0"


def test_matching_versions_are_accepted(tmp_path: Path) -> None:
    """Matching tag and metadata versions must pass."""
    validator = _load_validator()
    _write_project(tmp_path, "0.7.0")

    versions = validator.validate_release_version("v0.7.0", tmp_path)

    assert versions == {
        "tag": "0.7.0",
        "pyproject.toml": "0.7.0",
        "relinker.__version__": "0.7.0",
    }


def test_tag_mismatch_is_rejected(tmp_path: Path) -> None:
    """A release tag must never publish a differently versioned package."""
    validator = _load_validator()
    _write_project(tmp_path, "0.7.0")

    with pytest.raises(validator.VersionValidationError, match="version mismatch"):
        validator.validate_release_version("v0.7.1", tmp_path)


def test_package_mismatch_is_rejected(tmp_path: Path) -> None:
    """pyproject.toml and relinker.__version__ must agree."""
    validator = _load_validator()
    _write_project(tmp_path, "0.7.0")
    (tmp_path / "src" / "relinker" / "__init__.py").write_text(
        '__version__ = "0.7.1"\n',
        encoding="utf-8",
    )

    with pytest.raises(validator.VersionValidationError, match="version mismatch"):
        validator.validate_release_version("v0.7.0", tmp_path)
