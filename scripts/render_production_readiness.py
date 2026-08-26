#!/usr/bin/env python
"""Validate or render production readiness documentation from machine-collected evidence.

Usage:
    python scripts/render_production_readiness.py --check
    python scripts/render_production_readiness.py --evidence docs/release-evidence/<sha>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from marketing_mcp.readiness_evidence import validate_readiness_doc

DEFAULT_DOC = REPO_ROOT / "docs" / "PRODUCTION-READINESS.md"
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "docs" / "release-evidence"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC, help="path to PRODUCTION-READINESS.md")
    parser.add_argument("--evidence", type=Path, default=None, help="path to evidence json file")
    parser.add_argument("--check", action="store_true", help="verify doc claims against evidence")
    args = parser.parse_args(argv)

    if not args.doc.exists():
        print(f"Error: {args.doc} does not exist", file=sys.stderr)
        return 1

    doc_text = args.doc.read_text(encoding="utf-8")

    evidence_file = args.evidence
    if evidence_file is None:
        json_files = sorted(DEFAULT_EVIDENCE_DIR.glob("*.json"))
        if json_files:
            evidence_file = json_files[-1]

    evidence_bundle = {}
    if evidence_file and evidence_file.exists():
        evidence_bundle = json.loads(evidence_file.read_text(encoding="utf-8"))

    findings = validate_readiness_doc(doc_text, evidence_bundle)
    if findings:
        print("Readiness validation findings:", file=sys.stderr)
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("Production readiness doc validated successfully against machine evidence.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
