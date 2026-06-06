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
        "maintainers/architecture.md",
        "maintainers/stability-matrix.md",
        "maintainers/1.0-readiness.md",
        "maintainers/decisions/README.md",
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


def test_public_api_reference_documents_every_root_export() -> None:
    reference = (ROOT / "docs/reference/api.md").read_text(encoding="utf-8")
    missing = [name for name in relinker.__all__ if f"`{name}`" not in reference]

    assert missing == []


def test_public_api_reference_identifies_root_surface() -> None:
    reference = (ROOT / "docs/reference/api.md").read_text(encoding="utf-8")

    assert "relinker.__all__" in reference
    assert "from relinker.context import" in reference
    assert "relinker.__version__" in reference


def test_compatibility_guide_defines_public_api_tiers() -> None:
    compatibility = (ROOT / "docs/reference/compatibility.md").read_text(encoding="utf-8")

    assert "relinker.__all__" in compatibility
    assert "relinker.context.__all__" in compatibility
    assert "relinker.context._shared" in compatibility
    assert "relinker.internal" in compatibility
    assert "__version__" in compatibility


def test_compatibility_guide_documents_internal_scope() -> None:
    compatibility = (ROOT / "docs/reference/compatibility.md").read_text(encoding="utf-8")

    assert "relinker.__all__" in compatibility
    assert "relinker.internal" in compatibility
    assert "process-local" in compatibility


def test_readiness_record_does_not_invent_external_adoption() -> None:
    readiness = (ROOT / "docs/maintainers/1.0-readiness.md").read_text(encoding="utf-8")

    assert "Not recorded" in readiness
    assert "does not claim external adoption" in readiness


def test_documentation_index_contains_migration_guide() -> None:
    index = (ROOT / "docs/README.md").read_text(encoding="utf-8")

    assert "guides/migrating-to-1.0.md" in index
    assert (ROOT / "docs/guides/migrating-to-1.0.md").is_file()


def test_readme_does_not_say_alpha() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "status-alpha" not in readme
    assert "currently in alpha" not in readme


def test_compatibility_references_one_zero() -> None:
    compat = (ROOT / "docs/reference/compatibility.md").read_text(encoding="utf-8")

    assert "1.0.0" in compat


def test_release_docs_contain_one_zero_checklist() -> None:
    release = (ROOT / "docs/maintainers/release.md").read_text(encoding="utf-8")

    assert "1.0.0" in release
    assert "Checklist" in release


def test_migration_guide_internal_links_resolve() -> None:
    guide = ROOT / "docs/guides/migrating-to-1.0.md"
    content = guide.read_text(encoding="utf-8")

    import re
    from urllib.parse import unquote

    pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for raw_target in pattern.findall(content):
        target = raw_target.strip().split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        decoded = unquote(target)
        resolved = (guide.parent / decoded).resolve()
        assert resolved.exists(), f"Migration guide links to missing file: {resolved}"


def test_architectural_decision_records_have_required_sections() -> None:
    decision_files = (
        "docs/maintainers/decisions/001-public-api.md",
        "docs/maintainers/decisions/002-mutually-exclusive-exhaustion.md",
        "docs/maintainers/decisions/003-shared-retry-runtime.md",
        "docs/maintainers/decisions/004-context-package.md",
        "docs/maintainers/decisions/005-process-local-retry-budget.md",
    )

    for relative_path in decision_files:
        decision = (ROOT / relative_path).read_text(encoding="utf-8")
        for heading in (
            "## Context",
            "## Decision",
            "## Consequences",
            "## Alternatives considered",
        ):
            assert heading in decision
