# PyMC Marketing MCP

LLMs can explain marketing data. They should not invent marketing science

PyMC Marketing MCP gives MCP-compatible agents a controlled interface to Bayesian marketing science with PyMC-Marketing. The current v0.4.0 codebase covers dataset validation, MMM fitting, diagnostics, posterior contributions, total and marginal iROAS, scenario simulation, budget optimization, dynamic flighting, lift-test calibration, model comparison, CLV workflows, plots, lineage and asynchronous job tools

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

The repository is an **advanced beta with release-candidate implementation work**, not a release-approved production service

A large stabilization change on 2026-08-26 added local job persistence, security primitives, ownership helpers, structured logging, metrics and readiness checks. Those are meaningful implementation steps, but the broader production properties are not yet proven end to end for the current commit

Current blockers include

- remote HTTP authentication is not yet proven to propagate the real request principal into every MCP tool invocation
- MCP resources do not yet apply the same request principal, scope and ownership checks as protected tools
- ownership helpers exist, but resource creation/read paths still need full end-to-end ownership evidence
- asynchronous jobs currently execute inside the API process; production worker isolation, durable production repositories and crash recovery remain target work
- the dashboard API-key prototype still stores raw credentials independently of the server credential authority
- production CI, nightly statistical CI, compatibility canary and release workflows are not yet present
- there is no machine-generated release-evidence record for the current branch head
- committed agent eval fixtures still need conversion to executable trace evidence

Read these before making a production claim

- Documentation truth map: `docs/README.md`
- Current gate status: `docs/PRODUCTION-READINESS.md`
- Current capability inventory: `docs/CAPABILITIES.md`
- Hardening execution order: `docs/superpowers/plans/README.md`
- Release evidence rules: `docs/release-evidence/README.md`

New public capability work remains frozen until the stabilization gates and the 2026-08-26 hardening gates are proven from current-head evidence

## Current local/runtime capabilities

The supported local path uses Python 3.12 or 3.13, PyMC-Marketing 1.x, the MCP Python SDK 2.x, SQLite metadata/job state and local NetCDF/artifact storage

The public surface is generated from `src/marketing_mcp/capabilities.py`; do not maintain a hand-written tool count here

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
uv run ruff check src tests
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

Do not infer production readiness from a successful local HTTP start. Remote production mode additionally requires the security, storage, worker, observability and release-evidence gates in `docs/PRODUCTION-READINESS.md`

## Synthetic demo

```bash
uv run marketing-mcp-demo --fast
```

## Repository map

```text
src/marketing_mcp/
  mcp/            MCP tools, resources, envelopes and execution context
  services/       dataset, modeling, diagnostics, decision, plotting and CLV workflows
  domain/         validation, diagnostics policy, allocation and decision helpers
  adapters/       PyMC-Marketing computation boundary
  storage/        current SQLite/local artifact adapters and migrations
  jobs/           current SQLite job repository and in-process async executor
  security/       principals, scopes, ownership helpers, OAuth verifier and request safety
  observability/  logging and metrics foundations
  http/           health/readiness and request safety
  schemas/        typed Pydantic contracts
tests/
  statistical/    real PyMC-Marketing sampling and decision invariants
  integration/    protocol, persistence and lifecycle behavior
  contract/       public contract and decision-gate behavior
  release/        release-gate assertions
docs/
  README.md       documentation truth map
  superpowers/    stabilization and hardening plans
  release-evidence/ machine-collected release proof when generated
```

## Historical releases

Earlier v0.3 and v0.4 notes remain in `CHANGELOG.md` and `docs/FINAL-REVIEW.md` for provenance. They do not establish the readiness of the current commit
