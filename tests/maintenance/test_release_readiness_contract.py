"""Release readiness, repository hygiene, and pre-1.0 stabilization contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IGNORED_SCAN_PARTS = {".venv", ".git", "dist", "build"}


def _unreleased_block() -> str:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = changelog.index("## Unreleased")
    end = changelog.index("## 1.2.0")
    return changelog[start:end]


def _repository_matches(*patterns: str) -> list[Path]:
    matches: list[Path] = []
    for pattern in patterns:
        for path in ROOT.rglob(pattern):
            relative_parts = path.relative_to(ROOT).parts
            if IGNORED_SCAN_PARTS.isdisjoint(relative_parts):
                matches.append(path)
    return sorted(matches)


def test_changelog_has_unreleased_before_current_release() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "## Unreleased" in changelog
    assert changelog.index("## Unreleased") < changelog.index("## 1.2.0")


def test_changelog_one_two_records_released_changes() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = changelog.index("## 1.2.0")
    end = changelog.index("## 1.1.0")
    block = changelog[start:end]

    assert "DEFAULT_RETRYABLE_TRANSPORT_EXCEPTIONS" in block
    assert "implicit_default_policy" in block
    assert 'failure_mode="isolate"' in block


def test_changelog_one_one_history_remains_present() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    start = changelog.index("## 1.1.0")
    end = changelog.index("## 1.0.1")
    block = changelog[start:end]

    assert "RetryPolicy.named" in block
    assert "RetryPolicy.to_dict" in block
    assert "RetryBudgetSnapshot" in block


def test_changelog_history_remains_present_once() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    for heading in ("## 1.0.0", "## 0.8.0", "## 0.7.0", "## 0.6.1", "## 0.6.0", "## 0.4.0"):
        assert changelog.count(heading) == 1


def test_gitignore_contains_required_repository_hygiene_patterns() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".coverage",
        "htmlcov/",
        "build/",
        "dist/",
        "*.egg-info/",
        ".venv/",
        "CODEX_FASE*.md",
        "CODEX_FASES*.md",
        "*.patch.zip",
    ):
        assert pattern in gitignore


def test_gitignore_has_no_duplicate_useful_entries() -> None:
    entries = [
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    assert len(entries) == len(set(entries))


def test_temporary_patch_artifacts_are_not_in_repository() -> None:
    root_artifacts = (
        "PATCH_MANIFEST.md",
        "APPLYING_DOCS_PATCH.md",
        "APPLYING_RELINKER_PATCH.md",
        "APPLYING_PATCH.md",
    )
    for artifact in root_artifacts:
        assert not (ROOT / artifact).exists()

    assert _repository_matches("CODEX_FASE*.md", "CODEX_FASES*.md", "*.patch.zip") == []


def test_stabilization_documents_exist() -> None:
    for relative_path in (
        "docs/maintainers/stability-matrix.md",
        "docs/maintainers/1.0-readiness.md",
        "docs/maintainers/decisions/README.md",
        "docs/maintainers/decisions/001-public-api.md",
        "docs/maintainers/decisions/002-mutually-exclusive-exhaustion.md",
        "docs/maintainers/decisions/003-shared-retry-runtime.md",
        "docs/maintainers/decisions/004-context-package.md",
        "docs/maintainers/decisions/005-process-local-retry-budget.md",
    ):
        assert (ROOT / relative_path).is_file()


def test_release_readiness_scripts_exist() -> None:
    for relative_path in ("scripts/validate_installed_wheel.py", "benchmarks/smoke.py"):
        assert (ROOT / relative_path).is_file()


def test_installed_wheel_validator_uses_only_public_api() -> None:
    content = (ROOT / "scripts/validate_installed_wheel.py").read_text(encoding="utf-8")

    assert "relinker.internal" not in content
    assert "pytest" not in content
    for fragment in ("RetryBudget", "RetryPolicy", "retry", "asyncio.run"):
        assert fragment in content


def test_benchmark_smoke_is_not_a_ci_gate() -> None:
    content = (ROOT / "benchmarks/smoke.py").read_text(encoding="utf-8")

    for fragment in ("pytest", "assert elapsed <", "fail_under"):
        assert fragment not in content


def test_public_typing_examples_exist_and_use_public_api() -> None:
    for relative_path in (
        "tests/typing/basic_policy.py",
        "tests/typing/decorated_function.py",
        "tests/typing/async_policy.py",
        "tests/typing/context_manager.py",
        "tests/typing/public_api.py",
    ):
        content = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "from relinker" in content
        assert "type: ignore" not in content
        assert "relinker.internal" not in content


def test_one_zero_readiness_record_is_honest() -> None:
    readiness = (ROOT / "docs/maintainers/1.0-readiness.md").read_text(encoding="utf-8")

    assert "Not recorded" in readiness
    assert "does not claim external adoption" in readiness
    assert "technically prepared for version 1.0.0" in readiness
