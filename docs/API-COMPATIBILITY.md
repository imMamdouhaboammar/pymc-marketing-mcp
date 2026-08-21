# API & Ecosystem Compatibility Matrix

This document outlines the version requirements and API compatibility guarantees for PyMC Marketing MCP v0.3.0.

## Core Dependencies

| Package | Supported Versions | Tested Version | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | `>=3.12, <3.14` | `3.12.13` | CPython runtime with multithreaded BLAS/LAPACK |
| **pymc-marketing** | `>=1.0.0` | `1.0.0` | Unified `MMM`, `BudgetOptimizerWrapper`, `TimeSliceCrossValidator` |
| **pymc** | `>=6.0.0` | `6.0.1` | PyMC 6 sampling backend with PyTensor compiler |
| **arviz** | `>=0.21, <2.0` | `1.3.0` | Diagnostic summary (R-hat, ESS, divergences) |
| **xarray** | `>=2025.1` | `2026.7.0` | Multi-dimensional DataTree and Dataset backend |
| **h5netcdf** | `>=1.4.0` | `1.7.4` | NetCDF4 HDF5 backend for model serialization |
| **h5py** | `>=3.10.0` | `3.15.1` | HDF5 binary storage engine |
| **mcp** | `>=2.0.0, <3.0` | `2.0.0` | Official MCP Python SDK (stdio + Streamable HTTP) |
| **pydantic** | `>=2.12, <2.13` | `2.12.5` | Type validation, constraint checking, tool schemas |
| **pandas** | `>=2.2, <3.0` | `2.3.3` | Panel and tabular dataset ingestion |
| **numpy** | `>=2.0, <3.0` | `2.3.2` | Numerical computation |
| **uvicorn** | `>=0.34, <1.0` | `0.41.0` | Streamable HTTP ASGI host |

## API Evolution & Migration Guide

### 1. PyMC-Marketing 1.0.0 Unification
- **Previous (0.19.x)**: `pymc_marketing.mmm.multidimensional.MultidimensionalMMM` and separate wrapper modules.
- **Current (1.0.0)**: `from pymc_marketing.mmm import MMM, BudgetOptimizerWrapper, TimeSliceCrossValidator`. A single `MMM` class natively handles single-dimensional and multidimensional panel configurations through `dims=("geo",)`.

### 2. Model Persistence Format
- Model artifacts are serialized via `model.save(filepath)` using `h5netcdf` into standard NetCDF (`.nc`) files.
- `model.load(filepath)` reconstitutes the model instance, prior distributions, posterior traces, and dimensional coordinates.

### 3. Incrementality & Response API
- Total iROAS: `model.incrementality.contribution_over_spend(frequency="all_time")` returns `xarray.DataArray` with shape `(chain, draw, channel, *dims)`.
- Marginal iROAS: `model.incrementality.marginal_contribution_over_spend(frequency="all_time")` computes derivative at current operating point.
- Budget Scenario Simulation: `BudgetOptimizerWrapper(model=model, start_date=..., end_date=...).sample_response_distribution(allocation, noise_level=0.0, include_carryover=True)` returns `xarray.Dataset` with variable `total_media_contribution_original_scale`.
