"""Scientific core algorithms decoupled from MCP and network transport."""

from __future__ import annotations

from marketing_mcp.scientific.artifacts import (
    ArtifactManifest,
    SUPPORTED_ARTIFACT_KINDS,
    generate_mmm_artifacts,
)
from marketing_mcp.scientific.clv import (
    CLVFitResult,
    build_clv_purchase_from_spec,
    build_clv_value_from_spec,
    fit_clv_purchase_from_spec,
    fit_clv_value_from_spec,
)
from marketing_mcp.scientific.datasets import (
    inspect_dataset_frame,
    summarize_dataset_frame,
    validate_dataset_frame,
)
from marketing_mcp.scientific.decision_gate import (
    DecisionPolicyVerdict,
    enforce_decision_gate,
    evaluate_diagnostic_policy,
)
from marketing_mcp.scientific.mmm import (
    MMMFitResult,
    build_mmm_from_spec,
    extract_mcmc_diagnostics,
    extract_parameter_estimates,
    fit_mmm_from_spec,
)

__all__ = [
    "ArtifactManifest",
    "CLVFitResult",
    "DecisionPolicyVerdict",
    "MMMFitResult",
    "SUPPORTED_ARTIFACT_KINDS",
    "build_clv_purchase_from_spec",
    "build_clv_value_from_spec",
    "build_mmm_from_spec",
    "enforce_decision_gate",
    "evaluate_diagnostic_policy",
    "extract_mcmc_diagnostics",
    "extract_parameter_estimates",
    "fit_clv_purchase_from_spec",
    "fit_clv_value_from_spec",
    "fit_mmm_from_spec",
    "generate_mmm_artifacts",
    "inspect_dataset_frame",
    "summarize_dataset_frame",
    "validate_dataset_frame",
]
