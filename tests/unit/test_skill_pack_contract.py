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
    counts_by_type: dict[str, int] = {
        "should_trigger": 0,
        "should_not_trigger": 0,
        "ambiguous": 0,
        "multi_intent": 0,
        "recovery": 0,
    }
    for record in registry._records.values():
        assert record.package_dir is not None
        for relative in record.manifest.files.evals:
            payload = SkillEvalFile.model_validate_json(
                (record.package_dir / relative).read_text(encoding="utf-8")
            )
            for case in payload.routing_cases:
                routed, alternatives = registry.recommend(case.query)
                assert routed is not None
                assert isinstance(alternatives, list)
                counts_by_type[case.type] += 1
                if case.type == "should_trigger":
                    assert routed.manifest.name == case.expected_skill, case.id
                elif case.type == "should_not_trigger":
                    assert routed.manifest.name != record.manifest.name, case.id
                    if case.expected_skill:
                        assert routed.manifest.name == case.expected_skill, case.id
                elif case.type in {"ambiguous", "multi_intent", "recovery"}:
                    assert len(case.query) > 0
                    assert case.expected_behavior is not None
                checked += 1

    assert all(count > 0 for count in counts_by_type.values()), counts_by_type
    assert counts_by_type["should_trigger"] >= 20
    assert counts_by_type["should_not_trigger"] >= 11
    assert counts_by_type["ambiguous"] >= 11
    assert counts_by_type["multi_intent"] >= 11
    assert counts_by_type["recovery"] >= 11
    assert checked >= 64


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


def test_tool_trace_evaluator_edge_cases():
    from marketing_mcp.skillpack.evals import evaluate_tool_trace
    from marketing_mcp.skillpack.registry import ToolTrace

    # 1. Dict response envelope from diagnose_mmm should be parsed without crash
    dict_diag_trace = ToolTrace(
        id="dict-diagnose-envelope",
        expected_valid=True,
        steps=[
            {
                "tool": "diagnose_mmm",
                "result": {
                    "summary": {
                        "model_id": "mmm_1",
                        "decision_status": "approved",
                        "decision_tools_enabled": True,
                    }
                },
            },
            {"tool": "optimize_budget"},
        ],
    )
    eval_res = evaluate_tool_trace(dict_diag_trace)
    assert eval_res.valid is True

    # 2. submit_fit_mmm_job or resume_job after approved diagnosis resets decision gate
    async_reset_trace = ToolTrace(
        id="async-fit-resets-gate",
        expected_valid=False,
        steps=[
            {"tool": "diagnose_mmm", "result": "approved"},
            {"tool": "submit_fit_mmm_job"},
            {"tool": "optimize_budget"},
        ],
    )
    eval_res2 = evaluate_tool_trace(async_reset_trace)
    assert eval_res2.valid is False
    assert any(
        "optimize_budget called before an approved diagnostic gate" in r for r in eval_res2.reasons
    )

    # 3. Consecutive polling without declared max_consecutive_polls must be bounded by default
    unbounded_default_poll_trace = ToolTrace(
        id="unbounded-default-polling",
        expected_valid=False,
        steps=[
            {"tool": "poll_job_progress"},
            {"tool": "poll_job_progress"},
            {"tool": "poll_job_progress"},
            {"tool": "poll_job_progress"},
        ],
    )
    eval_res3 = evaluate_tool_trace(unbounded_default_poll_trace)
    assert eval_res3.valid is False
    assert any("unbounded polling" in r for r in eval_res3.reasons)


def test_tool_trace_evaluator_resume_authorization_contract():
    from marketing_mcp.skillpack.evals import evaluate_tool_trace
    from marketing_mcp.skillpack.registry import ToolTrace

    # 1. Resume without recovery after disconnect is rejected
    t1 = ToolTrace(
        id="resume-without-recovery",
        expected_valid=False,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {"tool": "resume_job", "arguments": {"job_id": "job-fit-1"}},
        ],
    )
    res1 = evaluate_tool_trace(t1)
    assert res1.valid is False
    assert any("resume_job called after disconnect" in r for r in res1.reasons)

    # 2. Resume after recovery with can_resume=False is rejected
    t2 = ToolTrace(
        id="resume-nonresumable",
        expected_valid=False,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "fit_mmm",
                    "status": "failed",
                    "can_resume": False,
                    "has_usable_result": False,
                },
            },
            {"tool": "resume_job", "arguments": {"job_id": "job-fit-1"}},
        ],
    )
    res2 = evaluate_tool_trace(t2)
    assert res2.valid is False
    assert any("can_resume=False" in r for r in res2.reasons)

    # 3. Resume when has_usable_result=True is rejected (should continue without resume)
    t3 = ToolTrace(
        id="resume-usable-result",
        expected_valid=False,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "fit_mmm",
                    "status": "succeeded",
                    "can_resume": False,
                    "has_usable_result": True,
                },
            },
            {"tool": "resume_job", "arguments": {"job_id": "job-fit-1"}},
        ],
    )
    res3 = evaluate_tool_trace(t3)
    assert res3.valid is False
    assert any("has_usable_result=True" in r for r in res3.reasons)

    # 4. Resume after recovery with can_resume=True and has_usable_result=False is authorized
    t4 = ToolTrace(
        id="resume-authorized",
        expected_valid=True,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "fit_mmm",
                    "status": "failed",
                    "can_resume": True,
                    "has_usable_result": False,
                },
            },
            {"tool": "resume_job", "arguments": {"job_id": "job-fit-1"}},
        ],
    )
    res4 = evaluate_tool_trace(t4)
    assert res4.valid is True

    # 5. Resume authorization is consumed/reset after invocation; second resume is rejected
    t5 = ToolTrace(
        id="resume-consumed-authorization",
        expected_valid=False,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "fit_mmm",
                    "status": "failed",
                    "can_resume": True,
                    "has_usable_result": False,
                },
            },
            {"tool": "resume_job", "arguments": {"job_id": "job-fit-1"}},
            {"tool": "resume_job", "arguments": {"job_id": "job-fit-1"}},
        ],
    )
    res5 = evaluate_tool_trace(t5)
    assert res5.valid is False
    assert any("without authoritative recovery" in r for r in res5.reasons)

    # 6. Resume with mismatched job_id is rejected
    t6 = ToolTrace(
        id="resume-mismatched-identity",
        expected_valid=False,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "fit_mmm",
                    "status": "failed",
                    "can_resume": True,
                    "has_usable_result": False,
                },
            },
            {
                "tool": "resume_job",
                "arguments": {"job_id": "job-different-2"},
            },
        ],
    )
    res6 = evaluate_tool_trace(t6)
    assert res6.valid is False
    assert any("but recovery authorized job 'job-fit-1'" in r for r in res6.reasons)

    # 7. Resume with matching job_id and valid MCP schema is valid
    t7 = ToolTrace(
        id="resume-matching-identity",
        expected_valid=True,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "fit_mmm",
                    "status": "failed",
                    "can_resume": True,
                    "has_usable_result": False,
                },
            },
            {"tool": "resume_job", "arguments": {"job_id": "job-fit-1"}},
        ],
    )
    res7 = evaluate_tool_trace(t7)
    assert res7.valid is True

    # 8. All six async submit tools are blocked post-disconnect without terminal recovery
    for submit_tool in (
        "submit_fit_mmm_job",
        "submit_transform_ad_export_job",
        "submit_budget_optimization_job",
        "submit_flighting_optimization_job",
        "submit_cross_validate_mmm_job",
        "submit_prior_sensitivity_job",
    ):
        t8 = ToolTrace(
            id=f"blocked-resubmit-{submit_tool}",
            expected_valid=False,
            steps=[
                {"tool": submit_tool},
                {"event": "disconnect"},
                {"tool": submit_tool},
            ],
        )
        res8 = evaluate_tool_trace(t8)
        assert res8.valid is False, (
            f"Expected {submit_tool} to be blocked post-disconnect without recovery"
        )
        assert any(
            "resubmitted after disconnect without authoritative terminal" in r for r in res8.reasons
        )

    # 9. All six async submit tools are permitted post-disconnect with terminal unrecoverable recovery
    for submit_tool, job_type in (
        ("submit_fit_mmm_job", "fit_mmm"),
        ("submit_transform_ad_export_job", "transform_ad_export"),
        ("submit_budget_optimization_job", "budget_optimize"),
        ("submit_flighting_optimization_job", "flighting_optimize"),
        ("submit_cross_validate_mmm_job", "cross_validate_mmm"),
        ("submit_prior_sensitivity_job", "prior_sensitivity"),
    ):
        t9 = ToolTrace(
            id=f"allowed-resubmit-{submit_tool}",
            expected_valid=True,
            steps=[
                {"tool": submit_tool},
                {"event": "disconnect"},
                {
                    "tool": "recover_execution_state",
                    "result": {
                        "job_id": f"job-{job_type}-1",
                        "job_type": job_type,
                        "status": "failed",
                        "can_resume": False,
                        "has_usable_result": False,
                    },
                },
                {"tool": submit_tool},
            ],
        )
        res9 = evaluate_tool_trace(t9)
        assert res9.valid is True, (
            f"Expected {submit_tool} to be permitted after terminal recovery, got {res9.reasons}"
        )

    # 10. Cross-family resubmissions post-recovery are strictly rejected
    t_cross = ToolTrace(
        id="cross-family-resubmit-budget-to-prior",
        expected_valid=False,
        steps=[
            {"tool": "submit_budget_optimization_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-budget-1",
                    "job_type": "budget_optimize",
                    "status": "failed",
                    "can_resume": False,
                    "has_usable_result": False,
                },
            },
            {"tool": "submit_prior_sensitivity_job"},
        ],
    )
    res_cross = evaluate_tool_trace(t_cross)
    assert res_cross.valid is False
    assert any("cross-family resubmission blocked" in r for r in res_cross.reasons)

    # 11. Unsupported arguments in resume_job are strictly rejected
    t_unsupported = ToolTrace(
        id="resume-unsupported-arg",
        expected_valid=False,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "fit_mmm",
                    "status": "failed",
                    "can_resume": True,
                    "has_usable_result": False,
                },
            },
            {
                "tool": "resume_job",
                "arguments": {"job_id": "job-fit-1", "job_type": "fit_mmm"},
            },
        ],
    )
    res_unsupported = evaluate_tool_trace(t_unsupported)
    assert res_unsupported.valid is False
    assert any("unsupported argument(s)" in r for r in res_unsupported.reasons)

    # 12. Mismatched recovered job type against originating submission is rejected
    t_mismatched_type = ToolTrace(
        id="resume-mismatched-originating-type",
        expected_valid=False,
        steps=[
            {"tool": "submit_fit_mmm_job"},
            {"event": "disconnect"},
            {
                "tool": "recover_execution_state",
                "result": {
                    "job_id": "job-fit-1",
                    "job_type": "budget_optimize",
                    "status": "failed",
                    "can_resume": True,
                    "has_usable_result": False,
                },
            },
            {
                "tool": "resume_job",
                "arguments": {"job_id": "job-fit-1"},
            },
        ],
    )
    res_mismatched_type = evaluate_tool_trace(t_mismatched_type)
    assert res_mismatched_type.valid is False
    assert any("does not match originating submission" in r for r in res_mismatched_type.reasons)
