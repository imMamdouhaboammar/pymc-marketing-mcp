# PyMC Marketing MCP

[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/imMamdouhaboammar/49445bb38f7e2e299235c6a04299e75f/raw/pymc_marketing_mcp_tests.json)](https://github.com/imMamdouhaboammar/pymc-marketing-mcp/actions)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/imMamdouhaboammar/49445bb38f7e2e299235c6a04299e75f/raw/pymc_marketing_mcp_coverage.json)](https://github.com/imMamdouhaboammar/pymc-marketing-mcp/actions)

LLMs can explain marketing data. They should not invent marketing science

PyMC Marketing MCP gives MCP-compatible agents a controlled interface to Bayesian marketing science with PyMC-Marketing. The current v0.4.0 codebase covers dataset validation, MMM fitting, diagnostics, posterior contributions, total and marginal iROAS, scenario simulation, budget optimization, dynamic flighting, lift-test calibration, model comparison, CLV workflows, plots, lineage, backend credential management, and durable asynchronous jobs

The boundary is intentional: the agent frames the business question and explains evidence, PyMC-Marketing computes model-dependent quantities, and this project owns input contracts, persistence, diagnostic policy, decision gating, authorization boundaries, output shaping and provenance

```text
User question
  -> AI agent
  -> MCP tool/resource
  -> validation + authorization
  -> application service
  -> PyMC-Marketing / PyMC / ArviZ
  -> posterior evidence
  -> diagnostic and decision policy
  -> structured result + warnings + provenance
```

## Current maturity

The repository is a **hardened release-candidate implementation** across Gates G0–G5 and H0–H6.

The 2026-08-26 core hardening program implemented and verified:
- Request-scoped identity propagation (`ContextVar[ExecutionContext]`) connecting authenticated HTTP principals directly to tool execution (Gate H1)
- Strict object and tenant authorization across all tools and MCP resources (Gate H2)
- Backend-controlled credential control plane (`CredentialService` and `/control/credentials`) storing only salted SHA-256 verifiers with immediate revocation (Gate H3)
- Durable background job persistence, canonical semantic idempotency hashing, and process-isolated worker execution (`marketing-mcp-worker`) (Gate H4)
- Structured JSON logging with secret scrubbing, low-cardinality metrics, and distributed trace propagation (Gate G4)
- Agent quality gates enforcing Bayesian decision gates and negative security evals (Gates AQG and H5)
- Upstream compatibility canary execution against the active PyMC-Marketing and ArviZ stack (Gate H6)

Read these for release and architecture details:

- Documentation truth map: `docs/README.md`
- Current gate status: `docs/PRODUCTION-READINESS.md`
- Current capability inventory: `docs/CAPABILITIES.md`
- Security architecture: `docs/SECURITY.md`
- Architecture overview: `docs/ARCHITECTURE.md`
- Decision integrity: `docs/DECISION-INTEGRITY.md`
- Release evidence: `docs/release-evidence/`

## Current local/runtime capabilities

The supported runtime uses Python 3.12 or 3.13, PyMC-Marketing 1.x (`>=1.0.0,<2`), the MCP Python SDK 2.x, SQLite metadata/jobs/credentials, and local NetCDF/artifact storage. Locked and release installs stay within this supported range. The upstream canary separately upgrades to the latest supported 1.x dependencies and probes the future 2.x major as an allowed-to-fail signal; neither lane changes the committed release lock or widens package metadata.

Support for PyMC-Marketing 2.x will be considered only after the adapter, statistical, plotting, optimization, calibration, and persisted-artifact suites pass against it and any intentional contract or artifact migration is documented.

The public capability surface is generated from `src/marketing_mcp/capabilities.py` (39 tools and resources)

Typical MMM flow

1. `register_dataset`
2. `inspect_dataset`
3. `validate_dataset`
4. `fit_mmm` or `submit_fit_mmm_job`
5. `diagnose_mmm`
6. inspect descriptive evidence
7. use decision-grade tools only when diagnostics permit them
8. retain model, dataset, configuration and package provenance in the final interpretation

Decision-grade outputs include scenario/optimization workflows and incremental ROAS. The exact gate contract is documented in `docs/DECISION-INTEGRITY.md`

## Install and verify

```bash
uv sync --frozen --extra dev
uv run pytest -m "not statistical" -v
uv run pytest -m statistical -v
uv run ruff check src tests scripts
uv run pyright
uv run python scripts/check_docs_drift.py
```

## Run locally with stdio

```bash
uv run marketing-mcp --transport stdio
```

Local stdio is intentionally treated as a trusted local principal

## Run Streamable HTTP for development

```bash
uv run marketing-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

## Run standalone background worker

```bash
uv run marketing-mcp-worker --poll-interval 2.0
```

## Synthetic demo

```bash
uv run marketing-mcp-demo --fast
```

## Repository map

```text
src/marketing_mcp/
  mcp/            MCP tools, resources, envelopes, context provider and task adapter
  services/       dataset, modeling, diagnostics, decision, plotting and CLV workflows
  domain/         validation, diagnostics policy, allocation and decision helpers
  adapters/       PyMC-Marketing computation boundary
  storage/        SQLite metadata, job and credential persistence
  credentials/    backend API key issuance, verifier hashing, and revocation
  jobs/           durable job models, semantic idempotency, process worker, and CLI
  security/       principals, scopes, authorization service, OAuth verifier, redaction
  observability/  structured JSON logging, metrics, and tracing
  http/           health, safety middleware, and credential control API
  schemas/        typed Pydantic contracts
tests/
  statistical/    real PyMC-Marketing sampling and decision invariants
  integration/    HTTP scope propagation, resource authorization, control API, and worker tests
  contract/       public contracts and decision-gate behavior
  release/        release-gate assertions (G0-G5, H0-H6)
  unit/           focused service and domain logic tests
docs/
  README.md       documentation truth map
  superpowers/    stabilization and hardening plans
  release-evidence/ machine-collected release proof
```

## Historical releases

Earlier v0.3 and v0.4 notes remain in `CHANGELOG.md` and `docs/FINAL-REVIEW.md` for provenance. They do not establish the readiness of the current commit
