"""Regression test ensuring releases validate the Git tag against package metadata."""

from __future__ import annotations

from pathlib import Path


def test_publish_workflow_executes_release_version_validator() -> None:
    """The tested release validator must actually be part of the publishing workflow."""
    project_root = Path(__file__).resolve().parents[2]
    workflow_path = project_root / ".github" / "workflows" / "publish.yml"
    workflow = workflow_path.read_text(encoding="utf-8")

    validator_path = "scripts/validate_release_version.py"
    validator_index = workflow.find(validator_path)

    assert validator_index >= 0, (
        "publish.yml must execute scripts/validate_release_version.py before publishing"
    )

    command_context = workflow[
        max(0, validator_index - 250) : validator_index + len(validator_path) + 250
    ]
    assert "RELEASE_TAG" in command_context, (
        "the release validator command must receive RELEASE_TAG"
    )
