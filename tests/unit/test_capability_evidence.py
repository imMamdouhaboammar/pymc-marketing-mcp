"""Evidence-integrity tests for the capability registry.

Slice 2.4 contract: a capability may only be promoted to ``stable`` when its declared delegate
matches the service call the MCP handler actually makes, and when at least one referenced evidence
test exercises that delegate. This prevents citing an unrelated passing test as proof.
"""

from __future__ import annotations

import ast
from pathlib import Path

from marketing_mcp.capabilities import get_capability_inventory

REPO_ROOT = Path(__file__).resolve().parents[2]


def _tool_handler_sources() -> dict[str, str]:
    """Map each MCP tool handler name to its source text.

    Handlers may live in server.py or any mcp/tools module after the
    boundary refactor, so scan the whole package.
    """
    package_dir = REPO_ROOT / "src" / "marketing_mcp" / "mcp"
    handlers: dict[str, str] = {}
    for path in sorted(package_dir.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                segment = ast.get_source_segment(source, node)
                if segment:
                    handlers[node.name] = segment
    return handlers


def test_every_tool_declares_the_delegate_its_handler_calls():
    handlers = _tool_handler_sources()
    problems: list[str] = []
    for capability in get_capability_inventory():
        if capability.kind != "tool":
            continue
        if not capability.delegates_to:
            problems.append(f"{capability.name}: no delegates_to declared")
            continue
        handler = handlers.get(capability.name)
        if handler is None:
            problems.append(f"{capability.name}: no handler named after the tool in server.py")
            continue
        expected = f"app.{capability.delegates_to}("
        if expected not in handler:
            problems.append(f"{capability.name}: handler does not call {expected}")
    assert not problems, "capability delegate drift:\n" + "\n".join(problems)


def test_stable_capability_evidence_exercises_its_delegate():
    problems: list[str] = []
    for capability in get_capability_inventory():
        if capability.status != "stable":
            continue
        if not capability.delegates_to:
            problems.append(f"{capability.name}: stable without a declared delegate")
            continue
        method = capability.delegates_to.split(".")[-1]
        exercised = False
        for test_id in capability.evidence_test_ids:
            test_file = REPO_ROOT / test_id.split("::")[0]
            if not test_file.exists():
                problems.append(f"{capability.name}: evidence file {test_file} is missing")
                continue
            if f".{method}(" in test_file.read_text(encoding="utf-8"):
                exercised = True
        if not exercised:
            problems.append(
                f"{capability.name}: no evidence test calls .{method}(); "
                f"cited {list(capability.evidence_test_ids)}"
            )
    assert not problems, "stable capability evidence does not exercise the delegate:\n" + "\n".join(
        problems
    )


def test_experimental_capabilities_are_the_only_unproven_ones():
    """Anything without evidence must be published as experimental — or as
    deprecated, since compatibility wrappers are intentionally unevidenced.
    Stable claims always require evidence."""
    for capability in get_capability_inventory():
        if not capability.evidence_test_ids:
            assert capability.status in ("experimental", "deprecated"), (
                f"{capability.name} claims status {capability.status!r} with no evidence tests"
            )


def test_registry_records_which_capabilities_have_real_statistical_evidence():
    """At least the core MMM decision path must be backed by real-library statistical tests."""
    statistical_evidence = {
        c.name
        for c in get_capability_inventory()
        if any("tests/statistical/" in t or "test_persistence_lifecycle" in t for t in c.evidence_test_ids)
    }
    required = {
        "fit_mmm",
        "diagnose_mmm",
        "get_channel_contributions",
        "get_incremental_roas",
        "simulate_budget",
        "optimize_budget",
    }
    assert required <= statistical_evidence, (
        "missing real statistical evidence for: " + str(sorted(required - statistical_evidence))
    )
