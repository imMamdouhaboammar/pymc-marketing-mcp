# PyMC Marketing MCP

LLMs can explain marketing data. They should not invent marketing science.

PyMC Marketing MCP gives MCP-compatible agents a controlled interface to Bayesian Marketing Mix Modeling with PyMC-Marketing. It handles dataset checks, MMM fitting, diagnostic gating, posterior contribution analysis, total and marginal iROAS, counterfactual spend scenarios, and constrained budget allocation while keeping the statistical computation inside PyMC-Marketing.

The core boundary is simple: the agent frames the business question and explains evidence. PyMC-Marketing computes the statistical quantities. The MCP layer validates inputs, persists artifacts, applies decision gates, reports uncertainty, and records provenance.

```text
User question
  -> AI agent
  -> MCP tool
  -> dataset / model validation
  -> PyMC-Marketing
  -> posterior evidence
  -> decision gate
  -> structured result + uncertainty + provenance
  -> AI explanation
```

## Production readiness

This project is currently an **advanced beta**, not a production-grade service. A production
stabilization program is in progress and new capability work is frozen until its release gates pass.

- Gates and current status: `docs/PRODUCTION-READINESS.md`
- Program spec: `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`
- Execution order: `docs/superpowers/plans/README.md`

Treat capability claims in this README and in `docs/` as verified only where a linked executable
test exists. Sections describing earlier releases are historical records, not current evidence.

## Version 0.3.0 highlights (historical)

Version `0.3.0` delivered comprehensive Bayesian statistical verification, model lineage, lift test calibration, cross-validation, and multi-core accelerated testing:

- **Time-Slice Cross-Validation**: `cross_validate_mmm` evaluates out-of-sample predictive accuracy across temporal folds with PyMC-Marketing's `TimeSliceCrossValidator`.
- **Prior Sensitivity Analysis**: `evaluate_prior_sensitivity` quantifies channel rank shifts under alternative adstock and saturation priors.
- **Lift Test Calibration**: `calibrate_mmm` incorporates real or synthetic experimental incrementality lift tests directly into model likelihood with full lineage tracking.
- **Extrapolation Risk Guard**: Spend scenarios or optimization allocations exceeding 1.5x historical 95th percentile spend automatically trigger actionable warnings.
- **Multi-Core Accelerated Testing**: Pytest suite runs concurrently via `pytest-xdist`, completing 46 unit, integration, and full Bayesian sampling tests in ~50 seconds.
- **Official MCP 2.0.0 Transports**: Fully tested stdio and Streamable HTTP clients with dynamic port discovery and structured error envelopes.

See `docs/DECISION-INTEGRITY.md` and `docs/VERIFICATION-MATRIX.md` for details.

## Current compatibility

- Python 3.12 to 3.13
- PyMC-Marketing `>=1.0.0`
- PyMC `>=6.0.0`
- ArviZ `>=0.21,<2.0`
- Official MCP Python SDK v2 (`mcp>=2.0.0`)
- NetCDF4 storage via `h5netcdf` and `h5py`
- CSV and Parquet datasets
- SQLite metadata and NetCDF model artifacts for local deployment

## Install

```bash
uv sync --extra dev
uv run pytest -n auto -v
```

## Run with stdio

```bash
uv run marketing-mcp --transport stdio
```

## Run with Streamable HTTP

```bash
uv run marketing-mcp --transport streamable-http --host 127.0.0.1 --port 8000
# endpoint: http://127.0.0.1:8000/mcp
```

## Docker

```bash
docker compose up --build
```

## Core flow

1. `register_dataset`
2. `inspect_dataset`
3. `validate_dataset`
4. `fit_mmm`
5. `diagnose_mmm`
6. `get_channel_contributions`
7. `get_incremental_roas`
8. `get_response_curves`
9. `simulate_budget`
10. `optimize_budget`
11. `cross_validate_mmm`
12. `evaluate_prior_sensitivity`
13. `calibrate_mmm`
14. `compare_models`
15. `archive_model`
16. Explain the posterior result, diagnostics, assumptions, and provenance

## Synthetic demo

```bash
uv run marketing-mcp-demo --fast
```

## Repository map

```text
src/marketing_mcp/
  mcp/            protocol tools + resources
  services/       application workflows (modeling, dataset, decision, diagnostics)
  domain/         validation, diagnostics engine & gate, allocation & extrapolation
  adapters/       PyMC-Marketing 1.0.0 boundary
  storage/        SQLite metadata + NetCDF artifacts
  schemas/        typed Pydantic contracts
tests/
  statistical/    real NUTS sampling, panel MMM, calibration, cross-validation
  integration/    MCP stdio/HTTP protocol, persistence lifecycle
  unit/           domain logic, failure datasets, security guardrails
docs/             architecture, contracts, safety, security, verification matrix
```
