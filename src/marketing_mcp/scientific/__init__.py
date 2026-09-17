"""Scientific core algorithms decoupled from MCP and network transport."""

from __future__ import annotations

from marketing_mcp.scientific.datasets import (
    inspect_dataset_frame,
    summarize_dataset_frame,
    validate_dataset_frame,
)
from marketing_mcp.scientific.mmm import (
    MMMFitResult,
    build_mmm_from_spec,
    extract_mcmc_diagnostics,
    extract_parameter_estimates,
    fit_mmm_from_spec,
)

__all__ = [
    "MMMFitResult",
    "build_mmm_from_spec",
    "extract_mcmc_diagnostics",
    "extract_parameter_estimates",
    "fit_mmm_from_spec",
    "inspect_dataset_frame",
    "summarize_dataset_frame",
    "validate_dataset_frame",
]
