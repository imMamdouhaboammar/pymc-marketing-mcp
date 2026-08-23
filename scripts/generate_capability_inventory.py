#!/usr/bin/env python
"""Generate or verify `docs/CAPABILITIES.md` from the capability registry.

Usage:
    python scripts/generate_capability_inventory.py            # write the document
    python scripts/generate_capability_inventory.py --check    # exit 1 on drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from marketing_mcp.capabilities import (
    get_capability_inventory,
    render_capability_markdown,
    validate_inventory,
)

DEFAULT_OUTPUT = REPO_ROOT / "docs" / "CAPABILITIES.md"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the document matches the registry instead of writing it",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"document path (default: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args(argv)

    inventory = get_capability_inventory()
    violations = validate_inventory(inventory)
    if violations:
        print("capability registry is invalid:", file=sys.stderr)
        for violation in violations:
            print(f"  - {violation}", file=sys.stderr)
        return 2

    expected = render_capability_markdown(inventory)

    if args.check:
        if not args.output.exists():
            print(f"drift: {args.output} does not exist", file=sys.stderr)
            return 1
        if args.output.read_text(encoding="utf-8") != expected:
            print(
                f"drift: {args.output} does not match the capability registry; "
                "regenerate it with `uv run python scripts/generate_capability_inventory.py`",
                file=sys.stderr,
            )
            return 1
        print(f"{args.output} matches the capability registry ({len(inventory)} capabilities)")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"wrote {args.output} ({len(inventory)} capabilities)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
