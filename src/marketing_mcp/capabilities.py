"""Explicit capability registry for every MCP tool and resource this server exposes.

This registry is the single source of truth for what the server *claims* to do. It is compared
against real MCP discovery by ``tests/integration/test_capability_inventory.py`` so that adding a
tool without declaring it — or declaring a tool that does not exist — fails the build.

Status vocabulary:

``experimental``
    The capability is exposed but its behavior is not yet proven by a referenced executable test.
    Agents and documentation must not present it as verified.

``stable``
    The capability's behavior is covered by at least one referenced executable evidence test.
    Statistically meaningful capabilities additionally require a real (non-mocked)
    PyMC-Marketing test.

``deprecated``
    Still exposed for compatibility, scheduled for removal.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field

CAPABILITY_KINDS: tuple[str, ...] = ("tool", "resource")
CAPABILITY_STATUSES: tuple[str, ...] = ("experimental", "stable", "deprecated")
CAPABILITY_DOMAINS: tuple[str, ...] = (
    "datasets",
    "modeling",
    "diagnostics",
    "decisions",
    "plots",
    "clv",
    "jobs",
    "artifacts",
    "insights",
    "skills",
)


@dataclass(frozen=True)
class Capability:
    """One publicly exposed MCP capability."""

    name: str
    kind: str
    domain: str
    status: str
    decision_gate_required: bool
    summary: str
    delegates_to: str = ""
    """Dotted ``Application`` attribute path the MCP handler calls, e.g. ``decisions.simulate``."""

    evidence_test_ids: tuple[str, ...] = field(default_factory=tuple)


def _tool(
    name: str,
    domain: str,
    summary: str,
    *,
    delegates_to: str,
    status: str = "experimental",
    decision_gate_required: bool = False,
    evidence_test_ids: tuple[str, ...] = (),
) -> Capability:
    return Capability(
        name=name,
        kind="tool",
        domain=domain,
        status=status,
        decision_gate_required=decision_gate_required,
        summary=summary,
        delegates_to=delegates_to,
        evidence_test_ids=evidence_test_ids,
    )


def _resource(
    name: str,
    domain: str,
    summary: str,
    *,
    delegates_to: str = "",
    status: str = "experimental",
    evidence_test_ids: tuple[str, ...] = (),
) -> Capability:
    return Capability(
        name=name,
        kind="resource",
        domain=domain,
        status=status,
        decision_gate_required=False,
        summary=summary,
        delegates_to=delegates_to,
        evidence_test_ids=evidence_test_ids,
    )


_INVENTORY: tuple[Capability, ...] = (
    # --- datasets ---------------------------------------------------------------------------
    _tool(
        "register_dataset",
        "datasets",
        "Register a CSV/Parquet file from the allowed ingest directory and fingerprint it.",
        delegates_to="datasets.register_file",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
            "tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists",
        ),
    ),
    _tool(
        "inspect_dataset",
        "datasets",
        "Report columns, dtypes, ranges, and candidate role assignments for a registered dataset.",
        delegates_to="datasets.inspect",
        status="stable",
        evidence_test_ids=(
            "tests/unit/test_dataset_service.py::test_register_and_inspect_dataset",
            "tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists",
        ),
    ),
    _tool(
        "list_datasets",
        "datasets",
        "List all registered datasets and available inbox files on the server.",
        delegates_to="datasets.list",
        status="stable",
        evidence_test_ids=(
            "tests/integration/test_data_ingestion_and_error_diagnostics.py::test_list_datasets_discovery",
        ),
    ),
    _tool(
        "validate_dataset",
        "datasets",
        "Check a dataset against MMM modeling requirements and report blocking issues.",
        delegates_to="datasets.validate",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
            "tests/integration/test_workflow_without_sampling.py::test_dataset_workflow_persists",
        ),
    ),
    _tool(
        "transform_ad_export",
        "datasets",
        "Pivot and transform raw ad-network export data into clean MMM modeling format with spend reconciliation.",
        delegates_to="datasets.transform_long_form",
        status="stable",
        evidence_test_ids=(
            "tests/unit/test_transform_ad_export_tool.py::test_transform_ad_export_tool_success_and_tenant_isolation",
            "tests/unit/test_raw_export_transformation.py::test_transform_long_form_export_pivot_and_aggregation",
        ),
    ),
    # --- modeling ---------------------------------------------------------------------------
    _tool(
        "fit_mmm",
        "modeling",
        "Fit a PyMC-Marketing MMM with the requested adstock/saturation configuration.",
        delegates_to="models.fit",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
            "tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts",
        ),
    ),
    _tool(
        "get_model_status",
        "modeling",
        "Report stored state, configuration, and diagnostics summary for a model.",
        delegates_to="models.status",
        status="stable",
        evidence_test_ids=(
            "tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts",
        ),
    ),
    _tool(
        "cross_validate_mmm",
        "modeling",
        "Evaluate out-of-sample accuracy with PyMC-Marketing time-slice cross-validation.",
        delegates_to="diagnostics.cross_validate",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_time_slice_cross_validation_and_prior_sensitivity",
        ),
    ),
    _tool(
        "evaluate_prior_sensitivity",
        "modeling",
        "Compare channel rankings under alternative adstock/saturation priors.",
        delegates_to="diagnostics.prior_sensitivity",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_time_slice_cross_validation_and_prior_sensitivity",
        ),
    ),
    _tool(
        "calibrate_mmm",
        "modeling",
        "Refit a model with experimental lift-test measurements added to the likelihood.",
        delegates_to="models.calibrate",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_lift_test_calibration_and_lineage",
        ),
    ),
    _tool(
        "compare_models",
        "modeling",
        "Compare stored models on configuration, diagnostics, and iROAS ordering.",
        delegates_to="models.compare_models",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_lift_test_calibration_and_lineage",
        ),
    ),
    _tool(
        "select_best_model",
        "modeling",
        "Rank models by information criterion and Bayesian model-averaging weights.",
        delegates_to="models.select_best_model",
    ),
    _tool(
        "archive_model",
        "modeling",
        "Mark a stored model as archived while preserving its artifact and lineage.",
        delegates_to="models.archive_model",
    ),
    # --- diagnostics ------------------------------------------------------------------------
    _tool(
        "diagnose_mmm",
        "diagnostics",
        "Run the mandatory sampler and posterior-predictive gate and set the decision status.",
        delegates_to="diagnostics.diagnose",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
            "tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts",
        ),
    ),
    # --- decisions --------------------------------------------------------------------------
    _tool(
        "get_channel_contributions",
        "decisions",
        "Report posterior channel contributions with uncertainty intervals.",
        delegates_to="decisions.contributions",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
        ),
    ),
    _tool(
        "get_incremental_roas",
        "decisions",
        "Report total and marginal incremental ROAS per channel with uncertainty.",
        decision_gate_required=True,
        delegates_to="decisions.iroas",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
        ),
    ),
    _tool(
        "get_response_curves",
        "decisions",
        "Report saturation response curves per channel.",
        delegates_to="decisions.response_curves",
    ),
    _tool(
        "simulate_budget",
        "decisions",
        "Evaluate a counterfactual spend scenario against the fitted baseline.",
        decision_gate_required=True,
        delegates_to="decisions.simulate",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
            "tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts",
        ),
    ),
    _tool(
        "optimize_budget",
        "decisions",
        "Allocate a fixed budget under channel constraints using the PyMC-Marketing optimizer.",
        decision_gate_required=True,
        delegates_to="decisions.optimize",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
            "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
            "tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts",
        ),
    ),
    _tool(
        "optimize_flighting",
        "decisions",
        "Build a multi-period weekly spend schedule and evaluate it against the model.",
        decision_gate_required=True,
        delegates_to="decisions.optimize_flighting",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_flighting_optimization.py::test_real_dynamic_flighting_optimization",
        ),
    ),
    _tool(
        "recommend_next_measurement",
        "decisions",
        "Suggest the next experiment or lift test that would most reduce decision uncertainty.",
        delegates_to="decisions.recommend_measurement",
    ),
    # --- plots ------------------------------------------------------------------------------
    _tool(
        "get_posterior_plots",
        "plots",
        "Render headless posterior plot artifacts (PNG/SVG) for a fitted model.",
        delegates_to="plots.generate_all",
    ),
    # --- clv --------------------------------------------------------------------------------
    _tool(
        "fit_purchase_model",
        "clv",
        "Fit a PyMC-Marketing purchase or churn frequency model (BG/NBD or Shifted Beta-Geometric).",
        delegates_to="clv.fit_purchase_model",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow",
            "tests/statistical/test_clv_real_models.py::test_real_shifted_beta_geo_workflow",
        ),
    ),
    _tool(
        "fit_value_model",
        "clv",
        "Fit a PyMC-Marketing monetary transaction value model (Gamma-Gamma).",
        delegates_to="clv.fit_value_model",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow",
        ),
    ),
    _tool(
        "predict_expected_purchases",
        "clv",
        "Predict future purchase frequency per customer from a fitted purchase model.",
        delegates_to="clv.predict_expected_purchases",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow",
        ),
    ),
    _tool(
        "predict_probability_alive",
        "clv",
        "Estimate probability of customer retention/alive from a fitted purchase or churn model.",
        delegates_to="clv.predict_probability_alive",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow",
            "tests/statistical/test_clv_real_models.py::test_real_shifted_beta_geo_workflow",
        ),
    ),
    _tool(
        "predict_expected_spend",
        "clv",
        "Predict average transaction monetary spend per customer from a fitted value model.",
        delegates_to="clv.predict_expected_spend",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow",
        ),
    ),
    _tool(
        "estimate_customer_lifetime_value",
        "clv",
        "Estimate discounted lifetime value by combining a purchase model and monetary value model.",
        delegates_to="clv.estimate_customer_lifetime_value",
        status="stable",
        evidence_test_ids=(
            "tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow",
        ),
    ),
    _tool(
        "fit_clv_model",
        "clv",
        "Fit a PyMC-Marketing CLV model (legacy compatibility wrapper).",
        delegates_to="clv.fit_clv",
        status="deprecated",
    ),
    _tool(
        "predict_customer_clv",
        "clv",
        "Produce customer-level predictions from a fitted CLV model (legacy compatibility wrapper).",
        delegates_to="clv.predict_clv",
        status="deprecated",
    ),
    _tool(
        "get_churn_risk_cohorts",
        "clv",
        "Group customers into churn-risk cohorts from a fitted CLV model.",
        delegates_to="clv.get_churn_risk_cohorts",
    ),
    # --- jobs -------------------------------------------------------------------------------
    _tool(
        "submit_fit_mmm_job",
        "jobs",
        "Submit an asynchronous MMM fitting job to run in the background without blocking.",
        delegates_to="jobs.submit_job",
        status="stable",
        evidence_test_ids=(
            "tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence",
        ),
    ),
    _tool(
        "submit_transform_ad_export_job",
        "jobs",
        "Submit an asynchronous ad export transformation job to pivot and reconcile spend in the background.",
        delegates_to="jobs.submit_job",
        status="stable",
        evidence_test_ids=(
            "tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence",
            "tests/unit/test_heavy_jobs_resilience.py::test_submit_transform_ad_export_job_idempotency_and_recovery",
        ),
    ),
    _tool(
        "submit_budget_optimization_job",
        "jobs",
        "Submit an asynchronous budget optimization job under channel constraints without blocking.",
        delegates_to="jobs.submit_job",
        status="stable",
        evidence_test_ids=(
            "tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence",
            "tests/unit/test_heavy_jobs_resilience.py::test_submit_budget_optimization_job_idempotency_and_recovery",
        ),
    ),
    _tool(
        "submit_flighting_optimization_job",
        "jobs",
        "Submit an asynchronous flighting optimization job across time periods and channels without blocking.",
        delegates_to="jobs.submit_job",
        status="stable",
        evidence_test_ids=(
            "tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence",
            "tests/unit/test_heavy_jobs_resilience.py::test_submit_flighting_optimization_job_idempotency_and_recovery",
        ),
    ),
    _tool(
        "submit_cross_validate_mmm_job",
        "jobs",
        "Submit an asynchronous cross-validation job for MMM out-of-sample evaluation.",
        delegates_to="jobs.submit_job",
        status="stable",
        evidence_test_ids=(
            "tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence",
            "tests/unit/test_heavy_jobs_resilience.py::test_submit_cross_validate_mmm_job_idempotency_and_recovery",
        ),
    ),
    _tool(
        "submit_prior_sensitivity_job",
        "jobs",
        "Submit an asynchronous prior sensitivity evaluation job comparing prior and posterior distributions.",
        delegates_to="jobs.submit_job",
        status="stable",
        evidence_test_ids=(
            "tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_job_submission_execution_and_persistence",
            "tests/unit/test_heavy_jobs_resilience.py::test_submit_prior_sensitivity_job_idempotency_and_recovery",
        ),
    ),
    _tool(
        "get_job_status",
        "jobs",
        "Retrieve the execution status, results, or error details of an asynchronous job.",
        delegates_to="jobs.get_job",
        status="stable",
        evidence_test_ids=(
            "tests/unit/test_job_state_machine.py::TestJobRepositoryAndService::test_create_and_retrieve_job",
        ),
    ),
    _tool(
        "cancel_job",
        "jobs",
        "Cancel a currently queued or running background job.",
        delegates_to="jobs.cancel_job",
        status="stable",
        evidence_test_ids=(
            "tests/unit/test_job_state_machine.py::TestJobRepositoryAndService::test_async_job_cancellation",
        ),
    ),
    _tool(
        "list_jobs",
        "jobs",
        "List recent asynchronous background jobs for the active tenant.",
        delegates_to="jobs.list_jobs",
        status="stable",
        evidence_test_ids=(
            "tests/release/test_g2_jobs_persistence.py::TestGateG2JobsPersistence::test_cross_tenant_job_access_blocked",
        ),
    ),
    _tool(
        "poll_job_progress",
        "jobs",
        "Non-blocking heartbeat poll waiting up to timeout_seconds for progress to avoid AI client timeout collapses.",
        delegates_to="jobs.poll_job",
        status="experimental",
    ),
    _tool(
        "recover_execution_state",
        "jobs",
        "Recover execution state and intermediate checkpoints after an unexpected disconnect or restart.",
        delegates_to="jobs.recover_job_state",
        status="experimental",
    ),
    _tool(
        "resume_job",
        "jobs",
        "Resume an interrupted or failed job from its last valid checkpoint without repeating completed work.",
        delegates_to="jobs.resume_job",
        status="experimental",
    ),
    _tool(
        "export_artifact_to_sandbox",
        "artifacts",
        "Push/stage a model or dataset artifact (up to 1GB) for the AI client sandbox to download.",
        delegates_to="artifacts.export_to_sandbox",
        status="experimental",
    ),
    _tool(
        "cleanup_server_storage",
        "artifacts",
        "Run server garbage collection to purge expired, delivered, or orphaned artifacts and temp files.",
        delegates_to="artifacts.cleanup_storage",
        status="experimental",
    ),
    _tool(
        "record_agent_insight",
        "insights",
        "Record structured findings, hypotheses, diagnostic warnings, or budget decisions.",
        delegates_to="insights.record_insight",
        status="stable",
        evidence_test_ids=("tests/unit/test_insight_service.py::test_insight_service_record_and_query",),
    ),
    _tool(
        "get_agent_insights",
        "insights",
        "Retrieve previously recorded agent insights, filterable by model, dataset, or category.",
        delegates_to="insights.list_insights",
        status="stable",
        evidence_test_ids=("tests/unit/test_insight_service.py::test_insight_service_record_and_query",),
    ),
    # --- scientific skill guidance ----------------------------------------------------------
    _tool(
        "get_skill_guidance",
        "skills",
        "Route a task to one scientific workflow skill or fetch one selected skill package.",
        delegates_to="skillpack.resolve_guidance",
        status="experimental",
    ),
    _tool(
        "list_agentic_skills",
        "skills",
        "List all registered agentic skills with summaries, maturity, and primary tools.",
        delegates_to="skillpack.catalog",
        status="experimental",
    ),
    _tool(
        "get_skill_workflow_map",
        "skills",
        "Retrieve the dependency graph, prerequisites, and decision gates for all scientific skills.",
        delegates_to="skillpack.workflow_map",
        status="experimental",
    ),
    # --- resources --------------------------------------------------------------------------
    _resource(
        "marketing://datasets/{dataset_id}",
        "datasets",
        "Registered dataset metadata and fingerprint.",
    ),
    _resource(
        "marketing://models/{model_id}",
        "modeling",
        "Stored model record, configuration, and provenance.",
    ),
    _resource(
        "marketing://models/{model_id}/diagnostics",
        "diagnostics",
        "Persisted diagnostics result and decision status for a model.",
    ),
    _resource(
        "marketing://models/{model_id}/lineage",
        "modeling",
        "Direct model record and parent_model_id provenance for a model.",
    ),
    _resource(
        "marketing://models/{model_id}/plots/{plot_type}",
        "plots",
        "Rendered posterior plot artifact for a model.",
        delegates_to="plots.get_cached_plot",
    ),
    _resource(
        "marketing://clv/{model_id}",
        "clv",
        "Stored CLV model record and configuration.",
    ),
    _resource(
        "marketing://skills",
        "skills",
        "Compact deterministic catalog of available scientific workflow skills.",
    ),
    _resource(
        "marketing://skills/{skill_name}",
        "skills",
        "Canonical operational SKILL.md content for one allowed skill name.",
    ),
    _resource(
        "marketing://skills/{skill_name}/manifest",
        "skills",
        "Machine-readable manifest for one allowed scientific workflow skill.",
    ),
    _resource(
        "marketing://skills/tool-map",
        "skills",
        "Machine-readable classification of every public MCP tool into skill guidance.",
    ),
    _resource(
        "marketing://skills/workflow-map",
        "skills",
        "Compact prerequisites, gates, continuations, and fallback workflow map.",
    ),
    _resource(
        "marketing://skills/decision-gates",
        "skills",
        "Decision-gated tool map derived from the public capability registry.",
    ),
    _resource(
        "marketing://skills/references/scientific-answer-contract",
        "skills",
        "Shared contract for communicating scientific analytical results and uncertainty.",
    ),
    _resource(
        "marketing://skills/references/scientific-source-ledger",
        "skills",
        "Versioned source ledger for scientific rules used by the Skill Pack.",
    ),
)


def get_capability_inventory() -> list[Capability]:
    """Return every declared capability, ordered by kind then name."""
    return sorted(_INVENTORY, key=lambda c: (c.kind, c.name))


def validate_inventory(
    inventory: Iterable[Capability],
    known_test_ids: Collection[str] | None = None,
) -> list[str]:
    """Return human-readable violations of the registry rules; empty means valid.

    Rules:
      1. ``kind``, ``status``, and ``domain`` come from the declared vocabularies.
      2. Names are unique.
      3. A ``stable`` capability references at least one evidence test.
      4. When ``known_test_ids`` is supplied, every referenced evidence test exists.
    """
    violations: list[str] = []
    seen: set[str] = set()
    for capability in inventory:
        label = f"{capability.kind} {capability.name}"
        if capability.name in seen:
            violations.append(f"{label}: duplicate capability name")
        seen.add(capability.name)
        if capability.kind not in CAPABILITY_KINDS:
            violations.append(f"{label}: unknown kind {capability.kind!r}")
        if capability.status not in CAPABILITY_STATUSES:
            violations.append(f"{label}: unknown status {capability.status!r}")
        if capability.domain not in CAPABILITY_DOMAINS:
            violations.append(f"{label}: unknown domain {capability.domain!r}")
        if capability.status == "stable" and not capability.evidence_test_ids:
            violations.append(f"{label}: status 'stable' requires at least one evidence test")
        if known_test_ids is not None:
            for test_id in capability.evidence_test_ids:
                if test_id not in known_test_ids:
                    violations.append(f"{label}: evidence test {test_id!r} does not exist")
    return violations


def get_capability(name: str) -> Capability:
    for capability in _INVENTORY:
        if capability.name == name:
            return capability
    raise KeyError(f"no capability record for {name!r}")


_DOC_HEADER = """# MCP Capability Inventory

<!-- GENERATED FILE - do not edit by hand. -->

This document is generated from `src/marketing_mcp/capabilities.py` by
`scripts/generate_capability_inventory.py`. Regenerate it with:

```bash
uv run python scripts/generate_capability_inventory.py
```

`tests/unit/test_capabilities_doc.py` fails when this file drifts from the registry, and
`tests/integration/test_capability_inventory.py` fails when the registry drifts from real MCP
discovery.

Status meanings:

- `experimental` — exposed, but behavior is not yet proven by a referenced executable test. Do not
  present it as verified.
- `stable` — behavior is covered by at least one referenced executable evidence test.
- `deprecated` — still exposed for compatibility, scheduled for removal.

`Decision gate` marks capabilities that the code refuses to execute until `diagnose_mmm` has
approved the model.
"""


def _evidence_cell(capability: Capability) -> str:
    if not capability.evidence_test_ids:
        return "none"
    return "<br>".join(f"`{test_id}`" for test_id in capability.evidence_test_ids)


def render_capability_markdown(inventory: Iterable[Capability]) -> str:
    """Render the capability registry as the canonical ``docs/CAPABILITIES.md`` content."""
    capabilities = sorted(inventory, key=lambda c: (c.kind, c.domain, c.name))
    lines = [_DOC_HEADER]

    counts: dict[str, int] = {}
    for capability in capabilities:
        counts[capability.status] = counts.get(capability.status, 0) + 1
    summary = ", ".join(
        f"{counts[status]} {status}" for status in CAPABILITY_STATUSES if status in counts
    )
    lines.append(f"\n**Totals:** {len(capabilities)} capabilities ({summary}).\n")

    for kind in CAPABILITY_KINDS:
        in_kind = [c for c in capabilities if c.kind == kind]
        if not in_kind:
            continue
        lines.append(f"\n## {kind.capitalize()}s\n")
        lines.append(
            "| Name | Domain | Status | Decision gate | Delegates to | Summary | Evidence tests |"
        )
        lines.append("|---|---|---|---|---|---|---|")
        for capability in in_kind:
            gate = "required" if capability.decision_gate_required else "not enforced"
            lines.append(
                f"| `{capability.name}` | {capability.domain} | {capability.status} | {gate} "
                f"| `{capability.delegates_to}` | {capability.summary} "
                f"| {_evidence_cell(capability)} |"
            )
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


__all__ = [
    "CAPABILITY_DOMAINS",
    "CAPABILITY_KINDS",
    "CAPABILITY_STATUSES",
    "Capability",
    "get_capability",
    "get_capability_inventory",
    "render_capability_markdown",
    "validate_inventory",
]
