# Architecture

## Principle

The MCP boundary stays thin. Protocol handlers translate controlled requests into application-service calls. Statistical computation belongs to PyMC-Marketing. This project owns contracts, data validation, persistence, diagnostic policy, allocation representation, output shaping, and provenance.

```text
MCP client
  -> MCP tools/resources
  -> Dataset / Modeling / Diagnostics / Decision services
  -> Decision allocation contracts
  -> PyMCMarketingAdapter
  -> PyMC-Marketing + PyMC + ArviZ
  -> artifact store (.nc) + SQLite metadata
```

## Domains

- Dataset service: registration, fingerprinting, inspection, MMM-specific validation, rectangular panel checks
- Modeling service: controlled configuration, fit lifecycle, persistence, package provenance
- Diagnostics service: divergences, R-hat, ESS, posterior predictive coverage/error, residual checks, decision state
- Decision allocation domain: historical baselines, channel and dimension-cell changes, allocation xarray conversion, constraint bounds
- Decision service: contribution, incrementality, response curves, scenarios, and allocation workflows
- PyMC adapter: official PyMC-Marketing computation boundary
- Storage ports: SQLite plus local artifacts now, replaceable by PostgreSQL/object storage later

## Budget data flow

```text
Historical model.X
  -> recent allocation by channel or channel x dims
  -> requested scenario OR constrained optimizer
  -> xarray allocation contract
  -> PyMC-Marketing response sampling
  -> posterior comparison
  -> compact JSON evidence
```

For models with dimensions such as `geo`, an allocation is represented over `channel x geo`. The domain layer verifies exact grid coverage before the adapter passes a DataArray to PyMC-Marketing.

## Compatibility

Version 0.2.0 targets PyMC-Marketing 0.19.4 through `<0.20` and uses the multidimensional MMM/budget wrapper path appropriate to that pinned line. A compatibility fallback is isolated inside the adapter for the wrapper rename. MCP targets the official Python SDK v2.

## Long-running work

The model record already persists `queued/running/completed/failed/cancelled`. Fitting currently executes within the tool call because the real MCP v2 Tasks behavior has not been exercised in this runtime. No proprietary polling protocol is presented as standards-compliant task support.
