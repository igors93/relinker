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


def _publish_job_blocks() -> dict[str, str]:
    project_root = Path(__file__).resolve().parents[2]
    workflow_path = project_root / ".github" / "workflows" / "publish.yml"
    lines = workflow_path.read_text(encoding="utf-8").splitlines()
    jobs_index = next(index for index, line in enumerate(lines) if line == "jobs:")
    blocks: dict[str, list[str]] = {}
    current_name: str | None = None

    for line in lines[jobs_index + 1 :]:
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            current_name = line.strip()[:-1]
            blocks[current_name] = [line]
        elif current_name is not None:
            blocks[current_name].append(line)

    return {name: "\n".join(block) for name, block in blocks.items()}


def test_publish_workflow_keeps_oidc_permissions_isolated_to_publish_job() -> None:
    blocks = _publish_job_blocks()

    assert set(blocks) == {"build", "publish"}
    assert "id-token: write" not in blocks["build"]
    assert "id-token: write" in blocks["publish"]
    assert "contents: write" not in blocks["publish"]
    assert "write-all" not in "\n".join(blocks.values())
    assert "needs: build" in blocks["publish"]
