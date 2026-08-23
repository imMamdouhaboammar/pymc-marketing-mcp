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
    evidence_test_ids: tuple[str, ...] = field(default_factory=tuple)


def _tool(
    name: str,
    domain: str,
    summary: str,
    *,
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
        evidence_test_ids=evidence_test_ids,
    )


def _resource(
    name: str,
    domain: str,
    summary: str,
    *,
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
        evidence_test_ids=evidence_test_ids,
    )


_INVENTORY: tuple[Capability, ...] = (
    # --- datasets ---------------------------------------------------------------------------
    _tool(
        "register_dataset",
        "datasets",
        "Register a CSV/Parquet file from the allowed ingest directory and fingerprint it.",
    ),
    _tool(
        "inspect_dataset",
        "datasets",
        "Report columns, dtypes, ranges, and candidate role assignments for a registered dataset.",
    ),
    _tool(
        "validate_dataset",
        "datasets",
        "Check a dataset against MMM modeling requirements and report blocking issues.",
    ),
    # --- modeling ---------------------------------------------------------------------------
    _tool(
        "fit_mmm",
        "modeling",
        "Fit a PyMC-Marketing MMM with the requested adstock/saturation configuration.",
    ),
    _tool(
        "get_model_status",
        "modeling",
        "Report stored state, configuration, and diagnostics summary for a model.",
    ),
    _tool(
        "cross_validate_mmm",
        "modeling",
        "Evaluate out-of-sample accuracy with PyMC-Marketing time-slice cross-validation.",
    ),
    _tool(
        "evaluate_prior_sensitivity",
        "modeling",
        "Compare channel rankings under alternative adstock/saturation priors.",
    ),
    _tool(
        "calibrate_mmm",
        "modeling",
        "Refit a model with experimental lift-test measurements added to the likelihood.",
    ),
    _tool(
        "compare_models",
        "modeling",
        "Compare stored models on configuration, diagnostics, and iROAS ordering.",
    ),
    _tool(
        "select_best_model",
        "modeling",
        "Rank models by information criterion and Bayesian model-averaging weights.",
    ),
    _tool(
        "archive_model",
        "modeling",
        "Mark a stored model as archived while preserving its artifact and lineage.",
    ),
    # --- diagnostics ------------------------------------------------------------------------
    _tool(
        "diagnose_mmm",
        "diagnostics",
        "Run the mandatory sampler and posterior-predictive gate and set the decision status.",
    ),
    # --- decisions --------------------------------------------------------------------------
    _tool(
        "get_channel_contributions",
        "decisions",
        "Report posterior channel contributions with uncertainty intervals.",
    ),
    _tool(
        "get_incremental_roas",
        "decisions",
        "Report total and marginal incremental ROAS per channel with uncertainty.",
    ),
    _tool(
        "get_response_curves",
        "decisions",
        "Report saturation response curves per channel.",
    ),
    _tool(
        "simulate_budget",
        "decisions",
        "Evaluate a counterfactual spend scenario against the fitted baseline.",
        decision_gate_required=True,
    ),
    _tool(
        "optimize_budget",
        "decisions",
        "Allocate a fixed budget under channel constraints using the PyMC-Marketing optimizer.",
        decision_gate_required=True,
    ),
    _tool(
        "optimize_flighting",
        "decisions",
        "Build a multi-period weekly spend schedule and evaluate it against the model.",
        decision_gate_required=True,
    ),
    _tool(
        "recommend_next_measurement",
        "decisions",
        "Suggest the next experiment or lift test that would most reduce decision uncertainty.",
    ),
    # --- plots ------------------------------------------------------------------------------
    _tool(
        "get_posterior_plots",
        "plots",
        "Render headless posterior plot artifacts (PNG/SVG) for a fitted model.",
    ),
    # --- clv --------------------------------------------------------------------------------
    _tool(
        "fit_clv_model",
        "clv",
        "Fit a PyMC-Marketing CLV model (BG/NBD, Gamma-Gamma, or shifted beta-geometric).",
    ),
    _tool(
        "predict_customer_clv",
        "clv",
        "Produce customer-level predictions from a fitted CLV model.",
    ),
    _tool(
        "get_churn_risk_cohorts",
        "clv",
        "Group customers into churn-risk cohorts from a fitted CLV model.",
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
        "Parent/child lineage chain for a model.",
    ),
    _resource(
        "marketing://models/{model_id}/plots/{plot_type}",
        "plots",
        "Rendered posterior plot artifact for a model.",
    ),
    _resource(
        "marketing://clv/{model_id}",
        "clv",
        "Stored CLV model record and configuration.",
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
        lines.append("| Name | Domain | Status | Decision gate | Summary | Evidence tests |")
        lines.append("|---|---|---|---|---|---|")
        for capability in in_kind:
            gate = "required" if capability.decision_gate_required else "not enforced"
            lines.append(
                f"| `{capability.name}` | {capability.domain} | {capability.status} | {gate} "
                f"| {capability.summary} | {_evidence_cell(capability)} |"
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
