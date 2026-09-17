"""Contract tests for the canonical scientific Skill Pack."""

from __future__ import annotations

from dataclasses import replace

import pytest

from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.errors import DomainError
from marketing_mcp.skillpack.registry import (
    EXPECTED_SKILLS,
    SkillRegistry,
    validate_tool_coverage,
)


def test_expected_skill_taxonomy_is_compact_and_complete():
    assert EXPECTED_SKILLS == (
        "pymc-artifact-delivery",
        "pymc-budget-optimization",
        "pymc-clv-customer-analytics",
        "pymc-dataset-readiness",
        "pymc-diagnostics-gate",
        "pymc-incrementality-evidence",
        "pymc-job-resilience",
        "pymc-lift-calibration",
        "pymc-marketing-router",
        "pymc-mmm-workflow",
        "pymc-model-validation",
    )


def test_registry_validates_manifests_frontmatter_and_support_files():
    registry = SkillRegistry.from_source_tree()
    assert registry.names() == EXPECTED_SKILLS
    assert registry.validate() == []


def test_every_public_tool_has_exactly_one_coverage_classification():
    registry = SkillRegistry.from_source_tree()
    tool_caps = [cap for cap in get_capability_inventory() if cap.kind == "tool"]
    report = validate_tool_coverage(registry.manifests(), tool_caps)
    assert report.errors == ()
    assert set(report.classification) == {cap.name for cap in tool_caps}
    assert all(report.classification[name]["classification"] for name in report.classification)


def test_fake_capability_causes_coverage_failure():
    registry = SkillRegistry.from_source_tree()
    existing = next(cap for cap in get_capability_inventory() if cap.kind == "tool")
    fake = replace(existing, name="future_unclassified_tool")
    report = validate_tool_coverage(registry.manifests(), [existing, fake])
    assert any("future_unclassified_tool" in error for error in report.errors)


def test_deprecated_capabilities_cannot_be_primary_tools():
    registry = SkillRegistry.from_source_tree()
    manifests = list(registry.manifests())
    deprecated = next(cap for cap in get_capability_inventory() if cap.status == "deprecated")
    target = manifests[0]
    bad_manifest = target.model_copy(
        update={"primary_tools": [*target.primary_tools, deprecated.name]}
    )
    bad = [bad_manifest, *manifests[1:]]
    report = validate_tool_coverage(bad, get_capability_inventory())
    assert any(deprecated.name in error and "deprecated" in error for error in report.errors)


def test_unknown_and_traversal_skill_names_fail_closed():
    registry = SkillRegistry.from_source_tree()
    for name in ("does-not-exist", "../.env", "%2e%2e/.env"):
        with pytest.raises(DomainError) as exc:
            registry.get(name)
        assert exc.value.code == "SKILL_NOT_FOUND"


def test_catalog_is_deterministic_compact_and_hashes_content():
    registry = SkillRegistry.from_source_tree()
    first = registry.catalog_json()
    second = registry.catalog_json()
    assert first == second
    assert len(first.encode("utf-8")) < 24_000
    assert '"content_hash"' in first


def test_behavioral_tool_traces_match_declared_validity():
    from marketing_mcp.skillpack.evals import evaluate_tool_trace
    from marketing_mcp.skillpack.registry import SkillEvalFile

    registry = SkillRegistry.from_source_tree()
    checked = 0
    for record in registry._records.values():
        assert record.package_dir is not None
        for relative in record.manifest.files.evals:
            payload = SkillEvalFile.model_validate_json(
                (record.package_dir / relative).read_text(encoding="utf-8")
            )
            for trace in payload.tool_traces:
                result = evaluate_tool_trace(trace)
                assert result.valid is trace.expected_valid, (
                    trace.id,
                    result.reasons,
                )
                checked += 1
    assert checked >= 6


def test_routing_evals_drive_the_runtime_router():
    from marketing_mcp.skillpack.registry import SkillEvalFile

    registry = SkillRegistry.from_source_tree()
    checked = 0
    for record in registry._records.values():
        assert record.package_dir is not None
        for relative in record.manifest.files.evals:
            payload = SkillEvalFile.model_validate_json(
                (record.package_dir / relative).read_text(encoding="utf-8")
            )
            for case in payload.routing_cases:
                routed, _ = registry.recommend(case.query)
                if case.type == "should_trigger":
                    assert routed.manifest.name == case.expected_skill, case.id
                    checked += 1
                elif case.type == "should_not_trigger":
                    assert routed.manifest.name != record.manifest.name, case.id
                    checked += 1
    assert checked >= 22


def test_required_resources_must_be_real_resource_capabilities():
    from marketing_mcp.skillpack.registry import SkillRecord

    source = SkillRegistry.from_source_tree()
    records = list(source._records.values())
    target = records[0]
    bad_manifest = target.manifest.model_copy(update={"required_resources": ["fit_mmm"]})
    records[0] = SkillRecord(
        manifest=bad_manifest,
        markdown=target.markdown,
        content_hash=target.content_hash,
        package_dir=target.package_dir,
    )
    bad_registry = SkillRegistry(records)
    errors = bad_registry.validate()
    assert any("unknown resource 'fit_mmm'" in error for error in errors)
