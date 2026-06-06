"""
Validate that a release tag matches every package version source.

This script is intended for local release checks and GitHub Actions. It avoids
third-party dependencies and reads version metadata without importing project
code, so validation cannot be affected by import-time side effects.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
import tomllib
from pathlib import Path


class VersionValidationError(RuntimeError):
    """Raised when release and package versions do not match."""


def normalize_release_tag(tag: str) -> str:
    """
    Convert a Git ref or release tag into its package-version form.

    Examples:
        `refs/tags/v0.7.0` becomes `0.7.0`.
        `v0.7.0` becomes `0.7.0`.
        `0.7.0` remains `0.7.0`.
    """
    normalized = tag.strip()

    if normalized.startswith("refs/tags/"):
        normalized = normalized.removeprefix("refs/tags/")

    normalized = normalized.removeprefix("v")

    if not normalized:
        raise VersionValidationError("release tag cannot be empty")

    return normalized


def read_pyproject_version(project_root: Path) -> str:
    """Read `[project].version` from pyproject.toml."""
    pyproject_path = project_root / "pyproject.toml"

    with pyproject_path.open("rb") as file:
        data = tomllib.load(file)

    try:
        version = data["project"]["version"]
    except KeyError as error:
        raise VersionValidationError(
            f"project version is missing from {pyproject_path}"
        ) from error

    if not isinstance(version, str) or not version:
        raise VersionValidationError(
            f"project version in {pyproject_path} must be a non-empty string"
        )

    return version


def read_package_version(project_root: Path) -> str:
    """
    Read `relinker.__version__` from the package source using the Python AST.

    Reading the assignment directly keeps release validation deterministic and
    avoids importing the package before the wheel has been built.
    """
    init_path = project_root / "src" / "relinker" / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))

    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue

        targets: list[ast.expr]
        value: ast.expr | None

        if isinstance(statement, ast.Assign):
            targets = statement.targets
            value = statement.value
        else:
            targets = [statement.target]
            value = statement.value

        if value is None:
            continue

        if any(isinstance(target, ast.Name) and target.id == "__version__" for target in targets):
            resolved = ast.literal_eval(value)
            if isinstance(resolved, str) and resolved:
                return resolved
            raise VersionValidationError(
                f"__version__ in {init_path} must be a non-empty string literal"
            )

    raise VersionValidationError(f"could not find __version__ in {init_path}")


def validate_release_version(tag: str, project_root: Path) -> dict[str, str]:
    """
    Validate the tag, pyproject.toml version, and package version.

    Returns the normalized values when they match. Raises
    `VersionValidationError` with a readable message when they differ.
    """
    versions = {
        "tag": normalize_release_tag(tag),
        "pyproject.toml": read_pyproject_version(project_root),
        "relinker.__version__": read_package_version(project_root),
    }

    if len(set(versions.values())) != 1:
        details = ", ".join(f"{name}={version!r}" for name, version in versions.items())
        raise VersionValidationError(f"version mismatch: {details}")

    return versions


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate a Relinker release tag against package metadata."
    )
    parser.add_argument(
        "--tag",
        default=os.environ.get("RELEASE_TAG"),
        help="Release tag, for example v0.7.0. Defaults to RELEASE_TAG.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root containing pyproject.toml and src/relinker.",
    )
    return parser.parse_args()


def main() -> int:
    """Run release-version validation from the command line."""
    args = parse_args()

    if args.tag is None:
        print(
            "release tag is required through --tag or RELEASE_TAG",
            file=sys.stderr,
        )
        return 2

    try:
        versions = validate_release_version(
            args.tag,
            args.project_root.expanduser().resolve(),
        )
    except (OSError, SyntaxError, ValueError, VersionValidationError) as error:
        print(f"release version validation failed: {error}", file=sys.stderr)
        return 1

    version = versions["pyproject.toml"]
    print(f"Verified Relinker release version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
