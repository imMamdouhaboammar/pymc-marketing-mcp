# API and Ecosystem Compatibility

This document describes the compatibility policy for PyMC Marketing MCP v0.4.0

Do not treat a hand-written tested-version table as release evidence. Declared ranges come from `pyproject.toml`; the exact environment for a release comes from `uv.lock` plus machine-generated current-commit evidence

## Declared runtime ranges

| Package | Declared range | Role |
|---|---|---|
| Python | `>=3.12,<3.14` | supported runtime, currently Python 3.12 and 3.13 |
| `pymc-marketing` | `>=1.0.0` | MMM, incrementality, optimizer and CLV computation boundary |
| `mcp[cli]` | `>=2,<3` | MCP Python SDK, stdio and Streamable HTTP |
| `pydantic` | `>=2.12,<2.13` | public input/output contracts |
| `pandas` | `>=2.2,<3` | tabular ingestion and manipulation |
| `numpy` | `>=2,<3` | numerical arrays |
| `xarray` | `>=2025.1` | posterior and multidimensional allocation structures |
| `arviz` | `>=0.21,<2` | posterior diagnostics and model comparison support |
| `h5netcdf` | `>=1.4.0` | NetCDF persistence backend |
| `h5py` | `>=3.10.0` | HDF5 support |
| `uvicorn` | `>=0.34,<1` | HTTP ASGI host |
| `structlog` | `>=25,<26` | structured logging foundation |
| `pyarrow` | `>=18,<24` | Parquet ingestion |
| `pyjwt` | `>=2.8,<3` | JWT validation primitives |

PyMC itself is currently supplied through the PyMC-Marketing dependency stack. Release evidence records the exact installed PyMC/PyTensor versions used by the statistical suite

## Exact tested environment

For a release candidate, obtain exact versions from

```bash
uv sync --frozen --extra dev
uv run python -c "from marketing_mcp import version_info; print(version_info())"
```

The release-evidence collector must record the same environment for the exact commit being assessed

No exact version in an old Markdown file overrides `uv.lock` or generated evidence

## PyMC-Marketing 1.x boundary

The adapter targets the PyMC-Marketing 1.x unified MMM APIs used by the current codebase, including model fitting, transforms, response sampling, incrementality, model comparison and CLV model families

Supported transform vocabulary is defined by the project Pydantic schemas and tested against real model construction. Documentation must not advertise an adstock or saturation transform that the schemas/adapter cannot construct

Model persistence uses the PyMC-Marketing save/load path with NetCDF-compatible artifacts

## Public compatibility layers

### MCP protocol

The server currently exposes

- stdio
- Streamable HTTP

The project has its own asynchronous job tools for current clients

- `submit_fit_mmm_job`
- `get_job_status`
- `cancel_job`
- `list_jobs`

These tools must not be described as standards-compliant MCP Tasks support

The target architecture keeps the internal JobService transport-neutral so a future MCP Tasks extension adapter can be added without changing the job state model

### Historical CLV wrappers

`fit_clv_model` and `predict_customer_clv` remain deprecated compatibility wrappers. New workflows should use the model-specific CLV tools listed in `docs/CAPABILITIES.md`

## Compatibility policy

A dependency change is accepted only when the relevant behavioral contracts pass, not only when imports succeed

Minimum canary coverage for upstream changes

1. import/constructor smoke for the PyMC-Marketing adapter
2. real small MMM fit
3. save/load round trip
4. diagnostic gate
5. incrementality/iROAS path
6. scenario + budget optimization path
7. multidimensional allocation path
8. CLV model smoke where affected
9. MCP discovery and stdio/HTTP round trip
10. capability/docs drift check

Statistical changes require real-library tests with explicit seed/tolerance where appropriate

## Production dependency policy target

The current `pymc-marketing>=1.0.0` lower-bound-only declaration is broader than the evidence policy we want for a production release

Before feature thaw/release

- define a bounded supported production range based on executed compatibility evidence
- keep a frozen production lock
- run a latest-allowed compatibility canary
- optionally run a non-blocking pre-release upstream lane
- never widen a dependency range automatically because one smoke test passed

See `docs/superpowers/plans/2026-08-26-upstream-compatibility-capability-gates.md`

## Release compatibility claim

A release may say a dependency combination is supported only when the exact or declared compatibility lane has current-head evidence

If a newer upstream version exists but has not passed the repository canary, it is not part of the verified production claim yet
