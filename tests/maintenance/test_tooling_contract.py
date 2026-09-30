"""Maintenance contracts for developer tooling and package hygiene.

Background: dev tools were declared with lower bounds only (``ruff>=0.15.15``).
Ruff 0.16 started formatting Python code blocks inside Markdown, so every CI
run failed at "Check formatting" and skipped all downstream jobs. The
pre-commit hook pinned a third, much older ruff. Separately, a stale
``src/relinker/.github`` directory was shipped inside the published wheel.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 only
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = ROOT / "src" / "relinker"
PINNED_TOOLS = ("ruff", "mypy")


def _dev_requirements() -> dict[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as file:
        dev = tomllib.load(file)["project"]["optional-dependencies"]["dev"]
    requirements: dict[str, str] = {}
    for requirement in dev:
        name = re.split(r"[<>=!~;\s\[]", requirement, maxsplit=1)[0]
        requirements[name.lower()] = requirement
    return requirements


@pytest.mark.parametrize("tool", PINNED_TOOLS)
def test_output_changing_dev_tools_are_pinned_exactly(tool: str) -> None:
    requirement = _dev_requirements()[tool]

    assert re.fullmatch(rf"{tool}==\d+(\.\d+)*", requirement), (
        f"{tool} must be pinned with == so a new release cannot break CI unannounced; "
        f"got {requirement!r}. Dependabot's python-dev-tools group bumps the pin."
    )


def test_pre_commit_ruff_matches_pyproject_pin() -> None:
    pinned = _dev_requirements()["ruff"].split("==", 1)[1]
    config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    match = re.search(r"astral-sh/ruff-pre-commit\s+rev:\s*v?(\S+)", config)

    assert match is not None, "ruff-pre-commit hook not found"
    assert match.group(1) == pinned


def test_local_lint_script_matches_ci_quality_steps() -> None:
    script = (ROOT / "scripts" / "lint.sh").read_text(encoding="utf-8")

    for fragment in (
        "python -m ruff format --check .",
        "python -m ruff check .",
        "python -m mypy src tests/typing",
    ):
        assert fragment in script


def test_package_source_contains_no_hidden_files() -> None:
    hidden = sorted(
        path.relative_to(PACKAGE_ROOT).as_posix()
        for path in PACKAGE_ROOT.rglob("*")
        if any(part.startswith(".") for part in path.relative_to(PACKAGE_ROOT).parts)
    )

    assert hidden == [], f"hidden files would be shipped inside the wheel: {hidden}"


def _load_wheel_validator() -> ModuleType:
    script_path = ROOT / "scripts" / "validate_installed_wheel.py"
    specification = importlib.util.spec_from_file_location("validate_installed_wheel", script_path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_wheel_validator_rejects_hidden_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = _load_wheel_validator()
    fake_package = tmp_path / "relinker"
    (fake_package / ".github" / "workflows").mkdir(parents=True)
    (fake_package / ".github" / "workflows" / "ci.yml").write_text("name: CI\n")
    (fake_package / "__init__.py").write_text("")
    (fake_package / "py.typed").write_text("")
    monkeypatch.setattr(validator.relinker, "__file__", str(fake_package / "__init__.py"))

    with pytest.raises(AssertionError, match=r"\.github/workflows/ci\.yml"):
        validator._validate_package_contents()


def test_wheel_validator_accepts_clean_package() -> None:
    _load_wheel_validator()._validate_package_contents()


def test_build_system_hatchling_matches_hashed_backend_lock() -> None:
    # Dependabot updates "/" (pyproject.toml) and "/requirements" separately, so
    # a bump in one place can silently leave the other on an older backend.
    with (ROOT / "pyproject.toml").open("rb") as file:
        requires = tomllib.load(file)["build-system"]["requires"]
    lock = (ROOT / "requirements" / "build-backend.txt").read_text(encoding="utf-8")
    locked = re.search(r"^hatchling==(\S+)", lock, re.MULTILINE)

    assert locked is not None, "hatchling must be pinned in requirements/build-backend.txt"
    assert requires == [f"hatchling=={locked.group(1)}"]
