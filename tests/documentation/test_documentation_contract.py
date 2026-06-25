"""Documentation structure, link, version, and public-import contracts."""

from __future__ import annotations

import ast
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
PYTHON_BLOCK = re.compile(r"```python\n(.*?)\n```", re.DOTALL)
SUPPORTED_PYTHON_RANGE = re.compile(r"Python\s+(3\.\d+)\s+through\s+Python\s+(3\.\d+)")


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


def _version_key(version: str) -> tuple[int, int]:
    major, minor = version.split(".", 1)
    return int(major), int(minor)


def _minor_versions_between(lower: str, upper: str) -> tuple[str, ...]:
    lower_major, lower_minor = _version_key(lower)
    upper_major, upper_minor = _version_key(upper)
    assert lower_major == upper_major == 3
    return tuple(f"3.{minor}" for minor in range(lower_minor, upper_minor + 1))


def _project_python_versions() -> tuple[str, ...]:
    with (ROOT / "pyproject.toml").open("rb") as file:
        classifiers = tomllib.load(file)["project"]["classifiers"]

    versions = [
        classifier.removeprefix("Programming Language :: Python :: ")
        for classifier in classifiers
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", classifier)
    ]
    return tuple(sorted(versions, key=_version_key))


def _ci_python_versions() -> tuple[str, ...]:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    match = re.search(r"python-version:\s*\[([^\]]+)\]", workflow)
    assert match is not None
    versions = re.findall(r'"(3\.\d+)"', match.group(1))
    return tuple(sorted(versions, key=_version_key))


def _documented_python_versions(path: Path) -> tuple[str, ...]:
    content = path.read_text(encoding="utf-8")
    match = SUPPORTED_PYTHON_RANGE.search(content)
    assert match is not None, f"{path.relative_to(ROOT)} does not document a Python range"
    return _minor_versions_between(*match.groups())


def _python_import_nodes(path: Path) -> list[tuple[int, int, ast.Import | ast.ImportFrom]]:
    imports: list[tuple[int, int, ast.Import | ast.ImportFrom]] = []
    for block_index, block in enumerate(PYTHON_BLOCK.findall(path.read_text(encoding="utf-8")), 1):
        tree = ast.parse(block, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import | ast.ImportFrom):
                imports.append((block_index, node.lineno, node))
    return imports


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


def test_documented_python_imports_are_executable() -> None:
    failures: list[str] = []
    markdown_files = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]

    for markdown_file in markdown_files:
        for block_index, line_number, node in _python_import_nodes(markdown_file):
            module = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
            try:
                exec(compile(module, str(markdown_file), "exec"), {})
            except Exception as error:
                failures.append(
                    f"{markdown_file.relative_to(ROOT)} block {block_index} "
                    f"line {line_number}: {error.__class__.__name__}: {error}"
                )

    assert failures == []


def test_supported_python_versions_match_metadata_ci_and_docs() -> None:
    expected = _project_python_versions()

    assert expected == ("3.10", "3.11", "3.12", "3.13", "3.14")
    assert _ci_python_versions() == expected
    assert _documented_python_versions(ROOT / "docs/reference/compatibility.md") == expected
    assert _documented_python_versions(ROOT / "README.md") == expected


def test_public_api_reference_documents_every_root_export() -> None:
    reference = (ROOT / "docs/reference/api.md").read_text(encoding="utf-8")
    missing = [name for name in relinker.__all__ if f"`{name}`" not in reference]

    assert missing == []


def test_public_api_reference_identifies_root_surface() -> None:
    reference = (ROOT / "docs/reference/api.md").read_text(encoding="utf-8")

    assert "relinker.__all__" in reference
    assert "from relinker.context import" in reference
    assert "relinker.__version__" in reference


def test_public_api_reference_does_not_claim_all_exports_existed_in_one_zero() -> None:
    reference = (ROOT / "docs/reference/api.md").read_text(encoding="utf-8")

    assert "All exports listed here are stable from `1.0.0`" not in reference
    assert "Individual exports may have been introduced" in reference


def test_release_checklist_allows_only_approved_public_api_additions() -> None:
    release = (ROOT / "docs/maintainers/release.md").read_text(encoding="utf-8")

    assert "Public API snapshots are unchanged." not in release
    assert (
        "Public API snapshots match the explicitly approved release surface for 1.3.1." in release
    )
    assert "No unplanned public API additions or removals are present." in release


def test_retry_after_docs_describe_large_values_as_capped_not_defaulted() -> None:
    guide = " ".join((ROOT / "docs/guides/http.md").read_text(encoding="utf-8").split())
    docstring = " ".join((relinker.parse_retry_after.__doc__ or "").split())

    assert "unusually large header values fall back" not in guide
    assert "excessively large header value falls back" not in docstring
    assert "large header values are capped" in guide
    assert "large header values are capped" in docstring


def test_retry_if_docstring_allows_none_as_a_real_return_value() -> None:
    docstring = " ".join((relinker.RetryPolicy.retry_if.__doc__ or "").split())

    assert "Exactly one is non-None" not in docstring
    assert "value may be None" in docstring


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


def test_compatibility_guide_documents_event_handlers_inspection_contract() -> None:
    compatibility = (ROOT / "docs/reference/compatibility.md").read_text(encoding="utf-8")

    assert "RetryPolicy.event_handlers" in compatibility
    assert "implementation detail" in compatibility
    assert "to_dict()" in compatibility


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


def test_introductory_docs_do_not_recommend_implicit_retry_defaults() -> None:
    for relative_path in ("README.md", "docs/guides/getting-started.md"):
        content = (ROOT / relative_path).read_text(encoding="utf-8")

        assert "@retry\ndef " not in content
        assert "RetryPolicy().run(" not in content


def test_compatibility_references_one_zero() -> None:
    compat = (ROOT / "docs/reference/compatibility.md").read_text(encoding="utf-8")

    assert "1.0.0" in compat


def test_release_docs_contain_one_zero_checklist() -> None:
    release = (ROOT / "docs/maintainers/release.md").read_text(encoding="utf-8")

    assert "1.3.1" in release
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
