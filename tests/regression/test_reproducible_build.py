"""Regression tests for Correction 6: reproducible build and publication.

These tests fail on the BEFORE state (open pins, no hashes, no lock, pip
upgrade present) and pass after the fix. Each test checks one contract:
- hatchling is pinned to an exact version
- pip upgrade step is absent from all CI workflows
- build-tools.txt uses hash-checked requirements
- build-tools.txt separates backend from test deps
- checksum is written at build and verified at publish
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
BUILD_TOOLS = ROOT / "requirements" / "build-tools.txt"
CI_YML = ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_YML = ROOT / ".github" / "workflows" / "publish.yml"
PYPROJECT = ROOT / "pyproject.toml"


# ---------------------------------------------------------------------------
# hatchling must be exactly pinned
# ---------------------------------------------------------------------------


class TestHatchlingPinned:
    def test_hatchling_exact_version_in_build_backend_lock(self) -> None:
        """hatchling must be listed with an exact version in requirements/build-backend.txt."""
        lock = ROOT / "requirements" / "build-backend.txt"
        assert lock.exists(), "requirements/build-backend.txt must exist to pin hatchling"
        content = lock.read_text()
        assert "hatchling==" in content, "hatchling must be pinned with == in build-backend.txt"

    def test_hatchling_pyproject_uses_exact_pin(self) -> None:
        """pyproject.toml [build-system].requires must list hatchling with == not >=."""
        content = PYPROJECT.read_text()
        # The line 'hatchling>=' is the problem — it must be 'hatchling=='
        assert "hatchling>=" not in content, (
            "pyproject.toml must not use hatchling>= — use an exact pin hatchling==X.Y.Z"
        )


# ---------------------------------------------------------------------------
# pip upgrade must not be present
# ---------------------------------------------------------------------------


class TestNoPipUpgrade:
    def _get_pip_upgrade_lines(self, path: Path) -> list[str]:
        lines = path.read_text().splitlines()
        return [
            line.strip()
            for line in lines
            if "pip install --upgrade pip" in line or "pip install -U pip" in line
        ]

    def test_ci_yml_has_no_pip_upgrade(self) -> None:
        """ci.yml must not upgrade pip at runtime."""
        bad = self._get_pip_upgrade_lines(CI_YML)
        assert not bad, (
            f"ci.yml still upgrades pip dynamically: {bad!r}. "
            "Remove or replace with a pinned pip install."
        )

    def test_publish_yml_has_no_pip_upgrade(self) -> None:
        """publish.yml must not upgrade pip at runtime."""
        bad = self._get_pip_upgrade_lines(PUBLISH_YML)
        assert not bad, (
            f"publish.yml still upgrades pip dynamically: {bad!r}. "
            "Remove or replace with a pinned pip install."
        )


# ---------------------------------------------------------------------------
# build-tools.txt must have hashes
# ---------------------------------------------------------------------------


class TestBuildToolsHashes:
    def test_build_tools_has_hash_lines(self) -> None:
        """requirements/build-tools.txt must use --hash= for reproducible installs."""
        content = BUILD_TOOLS.read_text()
        assert "--hash=sha256:" in content, (
            "build-tools.txt must include --hash=sha256: for each package "
            "to prevent supply chain attacks"
        )

    def test_build_tools_has_require_hashes(self) -> None:
        """build-tools.txt must contain --require-hashes so pip enforces hashes."""
        content = BUILD_TOOLS.read_text()
        assert "--require-hashes" in content, (
            "build-tools.txt must contain --require-hashes to enforce hash checking"
        )

    def test_build_tools_no_open_ranges(self) -> None:
        """build-tools.txt must not contain >= or ~= version specifiers."""
        content = BUILD_TOOLS.read_text()
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or not stripped:
                continue
            if stripped.startswith("-"):
                continue
            assert ">=" not in stripped and "~=" not in stripped, (
                f"build-tools.txt has open range on line: {stripped!r} — use ==X.Y.Z"
            )


# ---------------------------------------------------------------------------
# Artifact checksum must be verified between build and publish
# ---------------------------------------------------------------------------


class TestChecksumVerification:
    def test_publish_workflow_writes_checksum(self) -> None:
        """publish.yml build job must compute a SHA-256 checksum of dist artifacts."""
        content = PUBLISH_YML.read_text()
        has_sha = "sha256sum" in content or "hashlib" in content or "openssl dgst" in content
        assert has_sha, (
            "publish.yml build job must compute SHA-256 checksums of dist artifacts "
            "so the publish job can verify the same artifact was not tampered with"
        )

    def test_publish_workflow_verifies_checksum(self) -> None:
        """publish.yml publish job must verify the checksum written by the build job."""
        content = PUBLISH_YML.read_text()
        # At least two separate sha256 references: one to write, one to verify
        sha_count = content.count("sha256sum") + content.count("sha256")
        assert sha_count >= 2, (
            "publish.yml must verify checksum in both build and publish jobs "
            f"— only {sha_count} sha256 reference(s) found"
        )

    def test_publish_workflow_removes_checksum_manifest_before_pypi_publish(self) -> None:
        """publish.yml must not pass SHA256SUMS to the PyPI publish action."""
        content = PUBLISH_YML.read_text()

        verify_index = content.index("sha256sum --check dist/SHA256SUMS")
        remove_index = content.index("rm dist/SHA256SUMS")
        publish_index = content.index("pypa/gh-action-pypi-publish")

        assert verify_index < remove_index < publish_index
