"""Documentation structure, link, version, and public-import contracts."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

import relinker

ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _local_markdown_targets(path: Path) -> list[Path]:
    targets: list[Path] = []
    for raw_target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8")):
        target = raw_target.strip().split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        decoded = unquote(target)
        resolved = (ROOT / decoded) if decoded.startswith("/") else (path.parent / decoded)
        targets.append(resolved.resolve())
    return targets


def test_readme_does_not_duplicate_the_current_package_version() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "current package version is" not in readme
    assert "release history lives in" in readme


def test_project_version_sources_match() -> None:
    with (ROOT / "pyproject.toml").open("rb") as file:
        project_version = tomllib.load(file)["project"]["version"]

    assert relinker.__version__ == project_version


def test_internal_markdown_links_resolve() -> None:
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    missing: list[str] = []

    for markdown_file in markdown_files:
        for target in _local_markdown_targets(markdown_file):
            if not target.exists():
                missing.append(f"{markdown_file.relative_to(ROOT)} -> {target.relative_to(ROOT)}")

    assert missing == []


def test_documentation_index_contains_the_stability_guides() -> None:
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8")

    for relative_path in (
        "concepts/retry-lifecycle.md",
        "concepts/exhaustion.md",
        "reference/compatibility.md",
        "development/architecture.md",
    ):
        assert relative_path in index
        assert (ROOT / "docs" / relative_path).is_file()


def test_documented_core_imports_are_public() -> None:
    expected = {
        "RetryBudget",
        "RetryPolicy",
        "RetryResult",
        "RetryState",
        "TryAgain",
        "http_retry_policy",
        "network",
        "retry",
    }

    assert expected <= set(relinker.__all__)
    for name in expected:
        assert hasattr(relinker, name)


def test_compatibility_guide_documents_internal_scope() -> None:
    compatibility = (ROOT / "docs/reference/compatibility.md").read_text(encoding="utf-8")

    assert "relinker.__all__" in compatibility
    assert "relinker.internal" in compatibility
    assert "process-local" in compatibility
