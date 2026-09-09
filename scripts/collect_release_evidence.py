#!/usr/bin/env python
"""Collect machine-verified release evidence for the current commit.

Every command is executed here and its real exit code is recorded, so the resulting report cannot
contain a pass/fail claim that was not observed.

Usage:
    python scripts/collect_release_evidence.py                      # full verification set
    python scripts/collect_release_evidence.py --skip-statistical   # omit the slow sampling suite
    python scripts/collect_release_evidence.py --command "uv run ruff check src tests"
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from marketing_mcp.release_evidence import (
    collect_release_evidence,
    evidence_to_json,
    render_release_evidence_markdown,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "release-evidence"

FAST_COMMANDS = (
    'uv run pytest -n auto -q -m "not statistical"',
    "uv run ruff check src tests scripts",
    "uv run pyright",
    "uv run python scripts/generate_capability_inventory.py --check",
    "uv run python scripts/check_docs_drift.py",
)
STATISTICAL_COMMANDS = ("uv run pytest -m statistical -q",)


def _git_commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def _run(command: str) -> dict[str, object]:
    started = datetime.now(UTC)
    result = subprocess.run(
        command,
        shell=True,  # commands are repository-defined, not user input
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    duration = (datetime.now(UTC) - started).total_seconds()
    output = (result.stdout + result.stderr).strip().splitlines()
    tail = next(
        (line.strip() for line in reversed(output) if line.strip()),
        "",
    )
    print(f"[{result.returncode}] {command}\n    {tail}")
    return {
        "command": command,
        "exit_code": result.returncode,
        "stdout_tail": tail,
        "duration_seconds": round(duration, 2),
    }


def _hash_artifacts(dist_dir: Path) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    if not dist_dir.is_dir():
        return artifacts
    for path in sorted(dist_dir.iterdir()):
        if path.suffix not in {".whl", ".gz"}:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifacts.append({"name": path.name, "bytes": path.stat().st_size, "sha256": digest})
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--command",
        action="append",
        default=None,
        help="run only this command (repeatable); replaces the default verification set",
    )
    parser.add_argument(
        "--proof",
        action="append",
        default=[],
        help="approved proof id produced by one explicit --command (repeatable)",
    )
    parser.add_argument("--skip-statistical", action="store_true")
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--label", default=None, help="output file stem (default: commit SHA)")
    args = parser.parse_args(argv)

    commands = list(args.command) if args.command else list(FAST_COMMANDS)
    if args.proof and (not args.command or len(commands) != 1):
        parser.error("--proof requires exactly one explicit --command")
    if not args.command and not args.skip_statistical:
        commands += list(STATISTICAL_COMMANDS)
    if not args.command and not args.skip_build:
        commands.append("uv build")

    results = [_run(command) for command in commands]
    if args.proof:
        results[0]["proofs"] = args.proof
    artifacts = [] if args.command or args.skip_build else _hash_artifacts(REPO_ROOT / "dist")

    commit_sha = _git_commit_sha()
    evidence = collect_release_evidence(
        commit_sha,
        commands=results,
        artifacts=artifacts,
        collected_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        env=os.environ,
    )

    stem = args.label or commit_sha[:12]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{stem}.json"
    md_path = args.output_dir / f"{stem}.md"
    json_path.write_text(evidence_to_json(evidence), encoding="utf-8")
    md_path.write_text(render_release_evidence_markdown(evidence), encoding="utf-8")

    print(f"\nverdict: {evidence['verdict']}")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0 if evidence["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
