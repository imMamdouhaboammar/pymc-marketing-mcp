"""Experimental and benchmark-only Rust accelerator functions.

These functions are EXPLICITLY NOT for production statistical decisions.
They exist solely for:
  - Comparative benchmarks (Rust vs Python vs NumPy performance)
  - Parity testing (verifying Rust implementation matches Python output)
  - Algorithm correctness proofs in test suites

# IMPORTANT: Statistical Authority

Production MCMC diagnostic decisions are made exclusively by:
  marketing_mcp.domain.diagnostics.engine.diagnose_inferencedata

Using EXPERIMENTAL_ functions from this module for production decisions is a correctness bug.
The gate for downstream tools (budget optimization, scenario simulation) is gated on
Python/ArviZ diagnostic results, not on Rust approximations.

# Usage — correct
>>> from marketing_mcp.accelerators.experimental import EXPERIMENTAL_fast_mcmc_diagnostics
>>> # Only in tests and benchmarks:
>>> result = EXPERIMENTAL_fast_mcmc_diagnostics([1.01, 1.02], [450.0], 0)

# Usage — incorrect (will raise in production contexts)
>>> from marketing_mcp.services.decision_service import approve_budget
>>> rhats = run_pymc_sampling(...)
>>> EXPERIMENTAL_fast_compute_split_rhat(rhats)  # WRONG: never use for gate decisions
"""

from __future__ import annotations

import warnings
from typing import Any

from marketing_mcp.accelerators import (
    _IS_RUST_AVAILABLE,
    _py_fast_mcmc_diagnostics,
    _rust_core,
)


def EXPERIMENTAL_fast_mcmc_diagnostics(
    rhats: list[float], esses: list[float], divergences: int
) -> dict[str, Any]:
    """EXPERIMENTAL: Rust MCMC diagnostic evaluator for benchmarking only.

    Returns the same structure as the production diagnostics gate but has
    NO authority over downstream tool enabling or budget decisions.

    Use ONLY in benchmark scripts and parity tests.
    """
    warnings.warn(
        "EXPERIMENTAL_fast_mcmc_diagnostics is for benchmarking and parity tests only. "
        "It must never be used for production statistical gate decisions.",
        stacklevel=2,
        category=UserWarning,
    )
    if _IS_RUST_AVAILABLE and _rust_core and hasattr(_rust_core, "fast_mcmc_diagnostics"):
        return _rust_core.fast_mcmc_diagnostics(rhats, esses, divergences)
    return _py_fast_mcmc_diagnostics(rhats, esses, divergences)


def EXPERIMENTAL_fast_compute_split_rhat(chains: list[list[float]]) -> float:
    """EXPERIMENTAL: Rust split-R̂ computation for benchmarking only.

    Returns an approximation of split R-hat. NOT the authoritative production value.
    Production R-hat uses ArviZ which applies correct chain splitting, ESS corrections,
    and handles edge cases (constant chains, single-chain, etc.).

    Use ONLY in benchmark scripts and parity tests.
    """
    warnings.warn(
        "EXPERIMENTAL_fast_compute_split_rhat is for benchmarking only. "
        "Production R-hat authority belongs to ArviZ via diagnose_inferencedata.",
        stacklevel=2,
        category=UserWarning,
    )
    if _IS_RUST_AVAILABLE and _rust_core and hasattr(_rust_core, "fast_compute_split_rhat"):
        return float(_rust_core.fast_compute_split_rhat(chains))
    # Python fallback: naive variance-based approximation (not authoritative)
    all_vals = [v for chain in chains for v in chain]
    if not all_vals:
        return 1.0
    grand_mean = sum(all_vals) / len(all_vals)
    variance = sum((v - grand_mean) ** 2 for v in all_vals) / max(len(all_vals) - 1, 1)
    return 1.0 + max(0.0, variance - 1.0) / max(1.0, variance)


__all__ = [
    "EXPERIMENTAL_fast_compute_split_rhat",
    "EXPERIMENTAL_fast_mcmc_diagnostics",
]
