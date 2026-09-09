"""Tests for machine-derived production readiness status."""

from __future__ import annotations

import pytest

from marketing_mcp.readiness_evidence import (
    GateEvidence,
    parse_readiness_from_doc,
    render_readiness_table,
    validate_readiness_doc,
)

SAMPLE_EVIDENCE = [
    GateEvidence(
        gate="G0",
        name="Baseline Truth",
        status="evidence_pending",
        what_is_true="canonical version, capability inventory, tool-contract and docs-drift machinery exist",
        blockers="regenerate and execute current-head evidence after this documentation alignment",
        commit_sha="cb1d75d1fb82",
        evidence_file="docs/release-evidence/2026-08-26-current-head.md",
        tests=("tests/release/test_g0_production_truth.py",),
    ),
    GateEvidence(
        gate="G1",
        name="Scientific Correctness",
        status="partial",
        what_is_true="real PyMC-Marketing statistical suites cover MMM, CLV, flighting, model comparison",
        blockers="current-head machine evidence must rerun the full statistical suite and record dependency identity",
        commit_sha="cb1d75d1fb82",
        evidence_file="docs/release-evidence/2026-08-26-current-head.md",
        tests=("tests/release/test_g1_scientific_correctness.py",),
    ),
]


def test_render_readiness_table_formats_markdown():
    table = render_readiness_table(SAMPLE_EVIDENCE)
    assert "| Gate | Name | Current status | What is true today | What still blocks green |" in table
    assert "| G0 | Baseline Truth | evidence pending |" in table
    assert "| G1 | Scientific Correctness | partial |" in table


def test_green_gate_requires_commit_sha_and_passing_tests():
    invalid_green = GateEvidence(
        gate="G0",
        name="Baseline Truth",
        status="green",
        what_is_true="everything works",
        blockers="",
        commit_sha="",  # Missing SHA!
        evidence_file="",
        tests=(),
    )
    with pytest.raises(ValueError, match="cannot be green without commit_sha"):
        invalid_green.validate()


def test_validate_readiness_doc_rejects_unbacked_green_gates():
    doc_text = """
| Gate | Name | Current status | What is true today | What still blocks green |
|---|---|---|---|---|
| G0 | Baseline Truth | green | all good | none |
| G1 | Scientific Correctness | partial | models exist | stats pending |
"""
    evidence_bundle = {
        "commit_sha": "cb1d75d1fb82",
        "verdict": "FAIL",
        "gate_results": {
            "G0": {"status": "evidence_pending"},
        },
    }
    findings = validate_readiness_doc(doc_text, evidence_bundle)
    assert any("G0 marked green" in f for f in findings)


def test_green_gate_requires_matching_ci_candidate_provenance():
    doc_text = """
| Gate | Name | Current status | What is true today | What still blocks green |
|---|---|---|---|---|
| G0 | Baseline Truth | green | all good | none |
"""
    evidence_bundle = {
        "commit_sha": "a" * 40,
        "verdict": "PASS",
        "ci": {"is_ci": True, "candidate_matches": False},
        "gate_results": {"G0": {"status": "green"}},
    }
    findings = validate_readiness_doc(doc_text, evidence_bundle, expected_commit_sha="a" * 40)
    assert any("trusted CI candidate" in finding for finding in findings)


def test_green_gate_rejects_stale_evidence_commit():
    doc_text = """
| Gate | Name | Current status | What is true today | What still blocks green |
|---|---|---|---|---|
| G0 | Baseline Truth | green | all good | none |
"""
    evidence_bundle = {
        "commit_sha": "b" * 40,
        "verdict": "PASS",
        "ci": {"is_ci": True, "candidate_matches": True},
        "gate_results": {"G0": {"status": "green"}},
    }
    findings = validate_readiness_doc(doc_text, evidence_bundle, expected_commit_sha="a" * 40)
    assert any("does not match assessed commit" in finding for finding in findings)


def test_parse_readiness_from_doc_extracts_all_gates():
    doc_text = """
| Gate | Name | Current status | What is true today | What still blocks green |
|---|---|---|---|---|
| G0 | Baseline Truth | evidence pending | version exists | evidence run |
| G1 | Scientific Correctness | partial | stats suite exists | full suite |
| G2 | Service Recovery | partial | jobs exist | worker isolation |
"""
    parsed = parse_readiness_from_doc(doc_text)
    assert len(parsed) == 3
    assert parsed[0].gate == "G0"
    assert parsed[0].status == "evidence_pending"
    assert parsed[1].gate == "G1"
    assert parsed[2].gate == "G2"
