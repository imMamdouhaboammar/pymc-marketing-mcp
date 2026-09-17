#!/usr/bin/env python
"""Generate or verify packaged scientific Skill assets from canonical source packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.skillpack.registry import SkillEvalFile, SkillManifest, SkillRegistry

BUNDLE = REPO_ROOT / "src/marketing_mcp/skillpack/skill-bundle.json"
MANIFEST_SCHEMA = REPO_ROOT / ".agents/schemas/skill-package.schema.json"
EVAL_SCHEMA = REPO_ROOT / ".agents/schemas/skill-evals.schema.json"
SKILL_DOC = REPO_ROOT / "docs/SCIENTIFIC-SKILLS.md"


def _render_json(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _render_skill_doc(registry: SkillRegistry) -> str:
    tool_map = registry.tool_map()["tools"]
    manifests = {manifest.name: manifest for manifest in registry.manifests()}
    resource_users: dict[str, list[str]] = {}
    for manifest in manifests.values():
        for uri in manifest.required_resources:
            resource_users.setdefault(uri, []).append(manifest.name)

    lines = [
        "# Scientific Skill System",
        "",
        "<!-- GENERATED FILE - do not edit by hand. -->",
        "",
        "The canonical Agent Skill packages live under `.agents/skills/`. The MCP delivery layer",
        "packages the same validated content so remote clients can discover guidance lazily without",
        "a repository checkout. Agent Skills complement MCP schemas; they do not execute statistics.",
        "",
        "```text",
        "                 PyMC Marketing MCP",
        "                        |",
        "        +---------------+----------------+",
        "        |                                |",
        " MCP Execution Surface             Skill Knowledge Surface",
        " Tools / Resources                 Catalog / Skill Resources",
        "                                  Manifests / Maps / Router Tool",
        "        |                                |",
        "        +---------------+----------------+",
        "                        |",
        "                  AI Client / Host",
        "                        |",
        "                   User Question",
        "```",
        "",
        "## Discovery contract",
        "",
        "- `marketing://skills` is a compact deterministic catalog; it does not inline every skill.",
        "- `marketing://skills/{skill_name}` returns one canonical `SKILL.md` lazily.",
        "- `marketing://skills/{skill_name}/manifest` returns typed machine-readable routing metadata.",
        "- Tool/workflow/decision-gate maps are derived from the same manifests and capability registry.",
        "- `get_skill_guidance` is the model-callable fallback for hosts that do not surface resources to the model.",
        "- No non-standard `skills/list` protocol method is introduced.",
        "- MCP prompts are intentionally not added: the routing tool plus lazy resources is the smaller cross-host surface; prompts are user-selected in many clients and would duplicate workflow text.",
        "",
        "Clients should discover the catalog, select one skill, fetch only that skill, and load deeper references only when needed. Runtime Skill assets are bundled once at build time and cached in an immutable process registry.",
        "",
        "The installed MCP SDK v2 supports cache hints. The server applies private five-minute hints to discovery lists (`tools/list`, `resources/list`, and `resources/templates/list`) while leaving `resources/read` uncached globally so model/dataset resource semantics are unchanged. The Skill catalog is deterministically ordered and publishes stable catalog/content hashes for client-side reuse across reconnects.",
        "",
        "## Current-state capability / Skill matrix",
        "",
        "| Capability | MCP primitive | Status | Decision-gated | Existing skill / role | Gap |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for cap in get_capability_inventory():
        if cap.kind == "tool":
            entry = tool_map[cap.name]
            role = f"{entry['classification']}: " + ", ".join(entry["skills"])
        else:
            users = sorted(resource_users.get(cap.name, []))
            if users:
                role = "resource: " + ", ".join(users)
            elif cap.domain == "skills":
                role = "skill-delivery infrastructure"
            else:
                role = "shared MCP resource"
        gate = "yes" if cap.decision_gate_required else "no"
        lines.append(f"| `{cap.name}` | {cap.kind} | {cap.status} | {gate} | {role} | none |")
    lines += [
        "",
        "## Authority and safety",
        "",
        "Local source/tests define server policy; PyMC-Marketing, PyMC, and ArviZ define library semantics only where the server delegates to them. Model-dependent quantities must come from those executed/persisted outputs. Diagnostic approval is not causal proof, rejected decision gates cannot be bypassed with prompt arithmetic, uncertainty and caution states remain visible, and deprecated CLV wrappers are compatibility-only.",
        "",
        "See `.agents/references/scientific-source-ledger.md` and `.agents/references/scientific-answer-contract.md` for provenance and analytical communication rules.",
        "",
    ]
    return "\n".join(lines)


def generated_assets() -> dict[Path, str]:
    registry = SkillRegistry.from_source_tree(REPO_ROOT)
    errors = registry.validate()
    if errors:
        raise ValueError("invalid Skill Pack:\n" + "\n".join(f"- {e}" for e in errors))
    return {
        BUNDLE: _render_json(registry.bundle_payload()),
        MANIFEST_SCHEMA: _render_json(SkillManifest.model_json_schema()),
        EVAL_SCHEMA: _render_json(SkillEvalFile.model_json_schema()),
        SKILL_DOC: _render_skill_doc(registry),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    assets = generated_assets()

    if args.check:
        drift = [path for path, expected in assets.items() if not path.exists() or path.read_text() != expected]
        if drift:
            for path in drift:
                print(f"drift: {path.relative_to(REPO_ROOT)}", file=sys.stderr)
            return 1
        print(f"skill assets match canonical packages ({len(assets)} generated files)")
        return 0

    for path, content in assets.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
