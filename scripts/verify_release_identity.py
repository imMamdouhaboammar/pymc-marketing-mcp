#!/usr/bin/env python
"""Verify the release packaging identity of built artifacts and repository sources.

Given a directory of built artifacts (``uv build`` output), this checks that the wheel metadata
version matches the runtime version, the source distribution ships no vendored dependencies or
secrets, and the deployment script, Dockerfile, and dashboard agree on the version.

Usage:
    python scripts/verify_release_identity.py --dist-dir dist
    python scripts/verify_release_identity.py --dist-dir dist --commit "$GITHUB_SHA" \\
        --image-tag "$IMAGE_TAG"
"""

from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from marketing_mcp import __version__
from marketing_mcp.release_identity import DISTRIBUTION_NAME, verify_release_identity


def _wheel_version(dist_dir: Path) -> str | None:
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        return None
    with zipfile.ZipFile(wheels[-1]) as zf:
        metadata_name = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = zf.read(metadata_name).decode("utf-8")
    for line in metadata.splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    return None


def _sdist_members(dist_dir: Path) -> list[str] | None:
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if not sdists:
        return None
    with tarfile.open(sdists[-1]) as tar:
        return tar.getnames()


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=REPO_ROOT / "dist")
    parser.add_argument("--commit", default=None)
    parser.add_argument("--image-tag", default=None)
    args = parser.parse_args(argv)

    problems = verify_release_identity(
        runtime_version=__version__,
        wheel_version=_wheel_version(args.dist_dir),
        sdist_members=_sdist_members(args.dist_dir),
        deploy_script_text=_read(REPO_ROOT / "scripts" / "deploy_cloud_run.sh"),
        dockerfile_text=_read(REPO_ROOT / "Dockerfile"),
        dashboard_text=_read(REPO_ROOT / "dashboard" / "src" / "App.tsx"),
        image_tag=args.image_tag,
        commit_sha=args.commit,
    )

    if problems:
        print(f"release identity FAILED ({len(problems)} problem(s)):", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"release identity OK for {DISTRIBUTION_NAME} {__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
