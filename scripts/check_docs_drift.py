#!/usr/bin/env python
"""Fail when documentation claims something the code does not implement.

Usage:
    python scripts/check_docs_drift.py
    python scripts/check_docs_drift.py --root /path/to/checkout

`--root` relocates documentation and repository-owned declarative evidence such as
`pyproject.toml`. Checks backed by imported runtime code (package version, capability registry,
schemas, and transport constants) use the currently imported `marketing_mcp` package. Run this
script from the target checkout when those code-backed checks must also describe that checkout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from marketing_mcp.docs_drift import DOCUMENTED_DOCS, check_docs, discover_docs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT)
    args = parser.parse_args(argv)

    docs = DOCUMENTED_DOCS if args.root == REPO_ROOT else discover_docs(args.root)
    findings = check_docs(args.root, docs)
    if findings:
        print(f"documentation drift ({len(findings)} finding(s)):", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1

    print(f"no documentation drift across {len(docs)} document(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
