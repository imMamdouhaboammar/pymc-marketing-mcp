"""Unit tests for the capability registry validation rules.

Slice 2.2 contract: ``validate_inventory`` must reject a registry that marks a capability
``stable`` without referencing an executable evidence test, references a test that does not exist,
or uses an unknown domain/kind/status.
"""

from __future__ import annotations

from marketing_mcp.capabilities import (
    Capability,
    get_capability_inventory,
    validate_inventory,
)


def _capability(**overrides) -> Capability:
    base = {
        "name": "example_tool",
        "kind": "tool",
        "domain": "modeling",
        "status": "experimental",
        "decision_gate_required": False,
        "summary": "Example.",
        "evidence_test_ids": (),
    }
    base.update(overrides)
    return Capability(**base)


def test_stable_capability_without_evidence_is_rejected():
    violations = validate_inventory([_capability(status="stable")])
    assert any("evidence" in v for v in violations)


def test_stable_capability_with_evidence_is_accepted():
    known = {"tests/unit/test_example.py::test_thing"}
    violations = validate_inventory(
        [_capability(status="stable", evidence_test_ids=("tests/unit/test_example.py::test_thing",))],
        known_test_ids=known,
    )
    assert violations == []


def test_evidence_reference_to_a_missing_test_is_rejected():
    violations = validate_inventory(
        [_capability(status="stable", evidence_test_ids=("tests/unit/test_gone.py::test_gone",))],
        known_test_ids={"tests/unit/test_example.py::test_thing"},
    )
    assert any("test_gone" in v for v in violations)


def test_unknown_status_is_rejected():
    violations = validate_inventory([_capability(status="production-ready")])
    assert any("status" in v for v in violations)


def test_unknown_domain_is_rejected():
    violations = validate_inventory([_capability(domain="growth-hacking")])
    assert any("domain" in v for v in violations)


def test_unknown_kind_is_rejected():
    violations = validate_inventory([_capability(kind="prompt")])
    assert any("kind" in v for v in violations)


def test_duplicate_names_are_rejected():
    violations = validate_inventory([_capability(), _capability()])
    assert any("duplicate" in v for v in violations)


def test_experimental_capability_may_reference_evidence():
    known = {"tests/unit/test_example.py::test_thing"}
    violations = validate_inventory(
        [_capability(evidence_test_ids=("tests/unit/test_example.py::test_thing",))],
        known_test_ids=known,
    )
    assert violations == []


def test_real_inventory_satisfies_every_rule(known_test_node_ids):
    violations = validate_inventory(get_capability_inventory(), known_test_ids=known_test_node_ids)
    assert violations == []


def test_node_id_collector_resolves_module_and_class_level_tests(known_test_node_ids):
    """Self-check: a broken collector would make the evidence-existence rule vacuous."""
    assert (
        "tests/unit/test_capability_rules.py::"
        "test_node_id_collector_resolves_module_and_class_level_tests" in known_test_node_ids
    )
    assert (
        "tests/unit/test_model_selection.py::TestModelSelectionLogic::"
        "test_select_best_model_with_real_arviz_compare" in known_test_node_ids
    )
