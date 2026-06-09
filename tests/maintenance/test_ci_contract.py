"""Maintenance contracts for local and GitHub CI safeguards."""

from __future__ import annotations

import re
from collections import defaultdict
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


# ---------------------------------------------------------------------------
# GitHub Actions supply-chain contracts
# ---------------------------------------------------------------------------

WORKFLOW_DIR = ROOT / ".github" / "workflows"
REMOTE_ACTION_PATTERN = re.compile(
    r"^\s*uses:\s+(?P<action>[^@\s#]+)@(?P<reference>[^\s#]+)"
    r"(?:\s+#\s*(?P<version>\S.*))?$"
)
FULL_COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def _workflow_paths() -> list[Path]:
    return sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")))


def _remote_action_uses() -> list[tuple[Path, int, str, str, str | None]]:
    found: list[tuple[Path, int, str, str, str | None]] = []
    for workflow_path in _workflow_paths():
        for line_number, line in enumerate(
            workflow_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            match = REMOTE_ACTION_PATTERN.match(line)
            if match is None:
                continue
            action = match.group("action")
            if action.startswith("./") or action.startswith("docker://"):
                continue
            found.append(
                (
                    workflow_path,
                    line_number,
                    action,
                    match.group("reference"),
                    match.group("version"),
                )
            )
    return found


def _job_blocks(workflow_path: Path) -> dict[str, list[str]]:
    lines = workflow_path.read_text(encoding="utf-8").splitlines()
    jobs_index = next(index for index, line in enumerate(lines) if line == "jobs:")
    blocks: dict[str, list[str]] = {}
    current_name: str | None = None

    for line in lines[jobs_index + 1 :]:
        if line and not line.startswith(" "):
            break
        if re.fullmatch(r"  [A-Za-z0-9_-]+:", line):
            current_name = line.strip()[:-1]
            blocks[current_name] = [line]
        elif current_name is not None:
            blocks[current_name].append(line)

    return blocks


def test_remote_actions_are_pinned_to_full_commit_shas_with_version_comments() -> None:
    remote_actions = _remote_action_uses()

    assert remote_actions, "at least one remote GitHub Action must be present"
    for workflow_path, line_number, action, reference, version in remote_actions:
        location = f"{workflow_path.relative_to(ROOT)}:{line_number}"
        assert FULL_COMMIT_SHA_PATTERN.fullmatch(reference), (
            f"{location} must pin {action} to a full 40-character commit SHA"
        )
        assert version is not None and (
            version.startswith("v") or version.startswith("release/")
        ), f"{location} must keep a human-readable action version comment"


def test_repeated_actions_use_one_consistent_commit_sha() -> None:
    references: dict[str, set[str]] = defaultdict(set)
    for _path, _line_number, action, reference, _version in _remote_action_uses():
        references[action].add(reference)

    inconsistent = {
        action: sorted(action_references)
        for action, action_references in references.items()
        if len(action_references) > 1
    }
    assert inconsistent == {}


def test_every_workflow_job_has_a_positive_timeout() -> None:
    for workflow_path in _workflow_paths():
        blocks = _job_blocks(workflow_path)
        assert blocks, f"{workflow_path.relative_to(ROOT)} must define jobs"
        for job_name, block_lines in blocks.items():
            timeout_values = [
                int(match.group(1))
                for line in block_lines
                if (match := re.fullmatch(r"    timeout-minutes:\s*([0-9]+)", line))
            ]
            assert len(timeout_values) == 1, (
                f"{workflow_path.relative_to(ROOT)} job {job_name!r} "
                "must define exactly one timeout-minutes value"
            )
            assert timeout_values[0] > 0


def test_every_checkout_disables_persisted_credentials() -> None:
    for workflow_path in _workflow_paths():
        lines = workflow_path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            match = REMOTE_ACTION_PATTERN.match(line)
            if match is None or match.group("action") != "actions/checkout":
                continue

            use_indent = len(line) - len(line.lstrip())
            step_lines: list[str] = []
            for following in lines[index + 1 :]:
                stripped = following.lstrip()
                indent = len(following) - len(stripped)
                if stripped.startswith("- name:") and indent < use_indent:
                    break
                if stripped and indent < use_indent:
                    break
                step_lines.append(following)

            assert any(
                re.fullmatch(r"\s*persist-credentials:\s*false", step_line)
                for step_line in step_lines
            ), (
                f"{workflow_path.relative_to(ROOT)} checkout near line {index + 1} "
                "must set persist-credentials: false"
            )


def test_dependabot_keeps_github_actions_updates_enabled() -> None:
    dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")

    assert 'package-ecosystem: "github-actions"' in dependabot
    assert "schedule:" in dependabot
    assert "interval:" in dependabot
