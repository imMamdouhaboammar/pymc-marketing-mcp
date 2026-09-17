#!/usr/bin/env python
"""Validate canonical scientific Skill packages and tool coverage."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from marketing_mcp.skillpack.registry import SkillRegistry


def main() -> int:
    registry = SkillRegistry.from_source_tree(REPO_ROOT)
    errors = registry.validate()
    if errors:
        print(f"skill validation failed ({len(errors)} finding(s)):", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    tool_map = registry.tool_map()["tools"]
    print(
        f"validated {len(registry.names())} skills, {len(tool_map)} public tools, "
        f"catalog={len(registry.catalog_json().encode())} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
