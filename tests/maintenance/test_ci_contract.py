"""Maintenance contracts for local and GitHub CI safeguards."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_local_ci_script_runs_required_quality_package_and_coverage_steps() -> None:
    script = (ROOT / "scripts/ci.sh").read_text(encoding="utf-8")

    for fragment in (
        "python -m ruff format --check .",
        "python -m ruff check .",
        "python -m mypy src tests/typing",
        "python -m pytest",
        "--cov=relinker",
        "--cov-fail-under=85",
        "python -m build",
        "python -m twine check --strict dist/*",
    ):
        assert fragment in script


def test_github_workflow_preserves_supported_python_matrix() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for version in ('"3.10"', '"3.11"', '"3.12"', '"3.13"', '"3.14"'):
        assert version in workflow


def test_github_workflow_runs_required_quality_package_and_coverage_steps() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for fragment in (
        "python -m ruff format --check .",
        "python -m ruff check .",
        "python -m mypy src tests/typing",
        "--cov-fail-under=85",
        "python -m build",
        "python -m twine check --strict dist/*",
        "python scripts/validate_installed_wheel.py",
    ):
        assert fragment in workflow


def test_github_workflow_has_documentation_contract_job() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    for fragment in (
        "documentation:",
        "Documentation contracts",
        "tests/documentation",
        "tests/contracts/test_public_api_contract.py",
        "needs: [tests, documentation]",
    ):
        assert fragment in workflow


def test_wheel_smoke_test_uses_installed_wheel_validator() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "python scripts/validate_installed_wheel.py" in workflow
