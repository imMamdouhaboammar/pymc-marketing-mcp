"""Policy regressions for maintained, immutable GitHub Action runtimes."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)", re.MULTILINE)

# Verified upstream release metadata as of 2026-09-08. Composite and Docker
# actions are classified explicitly rather than mislabeled as Node actions.
APPROVED_ACTIONS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "node24"),
    "actions/deploy-pages": ("368f82528645a54fb793d4d04e342629a3f51346", "node24"),
    "actions/download-artifact": ("3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c", "node24"),
    "actions/upload-artifact": ("043fb46d1a93c77aae656e7c1c64a875d1fc6a0a", "node24"),
    "actions/upload-pages-artifact": ("fc324d3547104276b827a68afc52ff2a11cc49c9", "composite"),
    "astral-sh/setup-uv": ("20cfd1bf945f4377ade1205e4dbc17946fc9a30d", "node24"),
    "docker/build-push-action": ("53b7df96c91f9c12dcc8a07bcb9ccacbed38856a", "node24"),
    "docker/setup-buildx-action": ("37fe631027851001ddb9b187196cc803df7f5f0e", "node24"),
    "Schneegans/dynamic-badges-action": ("28b0fa8bdeb46170ac397105ece0c1fe58f68910", "node24"),
    "softprops/action-gh-release": ("efb35369e0ad2afab669f228072c1b0d510eae64", "node24"),
    "super-linter/super-linter/slim": ("4ce20838b8ab83717e78138c5b3a1407148e0918", "docker"),
    "The-PR-Agent/pr-agent": ("f3b385ea2927247ddcff2fe252472380b9c8f5fc", "docker"),
    "trufflesecurity/trufflehog": ("363923b901c911a9164f50b6c423f47c15372b1c", "composite"),
    "vn7n24fzkq/github-profile-summary-cards": (
        "d9632798b299e9ad6940449a859c30742eb5b549",
        "node24",
    ),
}


def _active_uses() -> list[tuple[Path, str, str]]:
    uses = []
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for value in USES_RE.findall(workflow.read_text(encoding="utf-8")):
            action, separator, ref = value.partition("@")
            assert separator, f"unversioned action in {workflow.name}: {value}"
            uses.append((workflow, action, ref))
    return uses


def test_all_active_actions_use_reviewed_immutable_runtime_refs() -> None:
    uses = _active_uses()

    assert len(uses) == 56
    assert {action for _, action, _ in uses} == set(APPROVED_ACTIONS)
    for workflow, action, ref in uses:
        expected_ref, _kind = APPROVED_ACTIONS[action]
        assert ref == expected_ref, f"unapproved {action}@{ref} in {workflow.name}"
        assert re.fullmatch(r"[0-9a-f]{40}", ref)


def test_runtime_inventory_distinguishes_node_composite_and_docker_actions() -> None:
    kinds = {action: kind for action, (_ref, kind) in APPROVED_ACTIONS.items()}

    assert sum(kind == "node24" for kind in kinds.values()) == 10
    assert sum(kind == "composite" for kind in kinds.values()) == 2
    assert sum(kind == "docker" for kind in kinds.values()) == 2
    assert "node20" not in kinds.values()
