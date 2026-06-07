"""Release contract for Relinker 1.0.1."""

from __future__ import annotations

import re
from pathlib import Path

import relinker

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[2]


def test_version_sources_report_one_zero_one() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project_version = tomllib.load(file)["project"]["version"]

    assert project_version == "1.0.1"
    assert relinker.__version__ == "1.0.1"


def test_classifier_is_production_stable() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        classifiers = tomllib.load(file)["project"]["classifiers"]

    classifier_text = "\n".join(classifiers)
    assert "Development Status :: 5 - Production/Stable" in classifier_text
    assert "Development Status :: 3 - Alpha" not in classifier_text


def test_changelog_has_dated_one_zero_one_section() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pattern = re.compile(r"^## 1\.0\.1 - \d{4}-\d{2}-\d{2}$", re.MULTILINE)
    matches = pattern.findall(changelog)

    assert len(matches) == 1


def test_changelog_unreleased_records_current_development_changes() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = changelog.index("## Unreleased")
    end = changelog.index("## 1.0.1")
    block = changelog[start + len("## Unreleased") : end].strip()

    assert "RetryPolicy.named" in block
    assert "RetryPolicy.to_dict" in block
    assert "RetryBudgetSnapshot" in block


def test_readme_is_stable() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "status-stable-brightgreen" in readme
    assert "Relinker 1.0" in readme
    assert "status-alpha" not in readme
    assert "currently in alpha" not in readme


def test_migration_guide_exists_with_required_sections() -> None:
    guide_path = ROOT / "docs/guides/migrating-to-1.0.md"
    assert guide_path.is_file()

    content = guide_path.read_text(encoding="utf-8")
    for fragment in (
        "Stable imports",
        "Exhaustion behavior",
        "Retry Budget",
        "Python support",
        "Deprecation policy",
    ):
        assert fragment in content


def test_compatibility_doc_is_post_one_zero() -> None:
    compat = (ROOT / "docs/reference/compatibility.md").read_text(encoding="utf-8")

    for fragment in (
        "Semantic versioning",
        "relinker.__all__",
        "relinker.context.__all__",
        "minor release",
        "major release",
        "process-local",
    ):
        assert fragment in compat


def test_public_api_size_is_unchanged() -> None:
    assert len(relinker.__all__) == 32


def test_readiness_record_is_honest() -> None:
    readiness = (ROOT / "docs/maintainers/1.0-readiness.md").read_text(encoding="utf-8")

    assert "Not recorded" in readiness
    assert "does not claim external adoption" in readiness
    assert "technically prepared for version 1.0.0" in readiness


def test_wheel_validator_checks_version() -> None:
    content = (ROOT / "scripts/validate_installed_wheel.py").read_text(encoding="utf-8")

    assert "distribution_version" in content
    assert "1.0.1" in content
