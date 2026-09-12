# PyMC Marketing MCP

[![Tests](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/imMamdouhaboammar/49445bb38f7e2e299235c6a04299e75f/raw/pymc_marketing_mcp_tests.json)](https://github.com/imMamdouhaboammar/pymc-marketing-mcp/actions)
[![Coverage](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/imMamdouhaboammar/49445bb38f7e2e299235c6a04299e75f/raw/pymc_marketing_mcp_coverage.json)](https://github.com/imMamdouhaboammar/pymc-marketing-mcp/actions)
![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)
![PyMC-Marketing](https://img.shields.io/badge/PyMC--Marketing-1.x-233D4D)
![MCP](https://img.shields.io/badge/MCP-2.x-111111)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

**Decision-safe Bayesian marketing science for MCP-compatible agents**

> LLMs can explain marketing data. They should not invent marketing science

PyMC Marketing MCP gives AI agents a controlled interface to [PyMC-Marketing](https://www.pymc-marketing.io/) for Marketing Mix Modeling, Bayesian decision support, experimentation, budget allocation, customer lifetime value, and durable analytical workflows

The design boundary is deliberate

- the agent frames the business question, chooses an allowed operation, and explains the evidence
- PyMC-Marketing, PyMC, and ArviZ compute model-dependent quantities
- this project owns validation, persistence, authorization, diagnostic policy, decision gates, provenance, jobs, and MCP contracts
- decision-grade actions stop when the statistical evidence is not strong enough

This is not a thin tool wrapper around a probabilistic library, and it is not an autonomous media-buying agent

---

## What you can do today

The current public registry contains **39 MCP capabilities: 25 stable, 12 experimental, and 2 deprecated**

The generated source of truth is [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md). Capability maturity is evidence-backed, so an exposed tool is not automatically considered stable

| Area | What the MCP can do | Representative capabilities |
| --- | --- | --- |
| Dataset readiness | Register, inspect, fingerprint, and validate modeling data | `register_dataset`, `inspect_dataset`, `validate_dataset` |
| MMM | Fit models, inspect status, compare models, calibrate with lift tests, and evaluate sensitivity | `fit_mmm`, `get_model_status`, `compare_models`, `calibrate_mmm`, `evaluate_prior_sensitivity` |
| Diagnostics | Run the mandatory statistical decision gate | `diagnose_mmm` |
| Measurement | Cross-validate models and suggest evidence-gathering work | `cross_validate_mmm`, `recommend_next_measurement` |
| Decision science | Contributions, incremental ROAS, scenarios, budget allocation, and weekly flighting | `get_channel_contributions`, `get_incremental_roas`, `simulate_budget`, `optimize_budget`, `optimize_flighting` |
| CLV | Purchase, churn, monetary-value, and lifetime-value modeling | `fit_purchase_model`, `fit_value_model`, `estimate_customer_lifetime_value` |
| Visual evidence | Produce posterior plot artifacts | `get_posterior_plots` |
| Durable work | Submit, inspect, list, cancel, and execute background jobs | `submit_fit_mmm_job`, `get_job_status`, `list_jobs`, `cancel_job` |
| Provenance | Inspect datasets, models, diagnostics, plots, CLV records, and model lineage through MCP resources | `marketing://...` resources |

Some capabilities above are still `experimental`. Check the generated inventory before treating a capability as verified behavior

---

## Why this project exists

A useful marketing agent needs more than access to a model

It needs a boundary between **reasoning about marketing** and **claiming a statistically supported decision**

```text
Business question
      |
      v
AI agent
      |
      v
MCP tool or resource
      |
      v
validation + authentication + tenant authorization
      |
      v
application service
      |
      v
PyMC-Marketing / PyMC / ArviZ
      |
      v
posterior evidence + diagnostics
      |
      v
decision policy
      |
      v
structured result + warnings + provenance
```

The model library owns the math. The MCP owns the rules around when that math may be used as decision evidence

---

## Decision safety is a runtime rule

The repository separates descriptive analytical outputs from decision-grade actions

For example, a fitted MMM is not automatically allowed to drive budget optimization. `diagnose_mmm` persists the current decision status, and gated tools such as `simulate_budget`, `optimize_budget`, and `optimize_flighting` refuse to execute when the model does not satisfy the decision contract

The important rule is simple

```text
model fitted != model approved for decisions
```

The gate does not claim that an approved model proves causal truth. It establishes whether the repository permits a defined class of downstream decisions under the current diagnostics contract

Read [`docs/DECISION-INTEGRITY.md`](docs/DECISION-INTEGRITY.md) and [`docs/STATISTICAL-SAFETY.md`](docs/STATISTICAL-SAFETY.md) before extending model-dependent decision behavior

---

## What the project deliberately does not do

The current runtime does not provide unrestricted autonomous marketing control

It does not

- let an LLM replace PyMC-Marketing for model-dependent calculations
- allow arbitrary shell, SQL, Python, or callback execution through MCP tools
- bypass diagnostics because a caller asks to "continue anyway"
- change priors, model families, variables, or diagnostic thresholds until a model passes
- treat a recent KPI movement as proof that something is broken
- mutate Google Ads, Meta Ads, LinkedIn Ads, or other ad-platform campaigns as a current public capability
- infer production readiness from the presence of tests or planning documents

These restrictions are product behavior, not prompt conventions

---

## Quick start

### Requirements

- Python 3.12 or 3.13
- [`uv`](https://docs.astral.sh/uv/)

### Install the development environment

```bash
git clone https://github.com/imMamdouhaboammar/pymc-marketing-mcp.git
cd pymc-marketing-mcp
uv sync --frozen --extra dev
```

### Run the synthetic demo

```bash
uv run marketing-mcp-demo --fast
```

### Start the MCP server over stdio

```bash
uv run marketing-mcp --transport stdio
```

Local stdio intentionally runs as a trusted local principal. Use an authenticated security profile for remote HTTP access

---

## Runtime modes

### Local stdio

Use this for local MCP clients and development

```bash
uv run marketing-mcp --transport stdio
```

### Local Streamable HTTP

Use loopback HTTP for development

```bash
uv run marketing-mcp \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8000
```

The runtime exposes the MCP endpoint at `/mcp`, plus `/health`, `/health/live`, and `/health/ready`

### Private HTTP with an API key

The `http-private-api-key` profile requires authentication before startup

```bash
export MARKETING_MCP_SECURITY_PROFILE=http-private-api-key
export MARKETING_MCP_API_KEY='replace-with-a-real-secret'

uv run marketing-mcp \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8000
```

Do not commit credentials or place them in examples, fixtures, logs, screenshots, or release evidence

### Production OAuth profile

The codebase includes an `http-production-oauth` profile with asymmetric token verification, required scopes, and tenant claim mapping

Production deployment is **not release-approved**. External identity-provider integration and exact-commit release evidence remain part of the production-readiness contract

Use [`docs/SECURITY.md`](docs/SECURITY.md), [`docs/DEPLOYMENT-GCP.md`](docs/DEPLOYMENT-GCP.md), and [`docs/PRODUCTION-READINESS.md`](docs/PRODUCTION-READINESS.md) instead of treating this README as a production deployment runbook

---

## Background jobs

Expensive statistical work can be represented as durable jobs rather than tying computation to one MCP request

Run a standalone worker with

```bash
uv run marketing-mcp-worker --poll-interval 2.0
```

The current job implementation includes durable job records, semantic idempotency, cancellation, leases, fencing, retry limits, and stale-lease recovery

Production claims about distributed workers remain subject to the G2 and H4 evidence requirements in [`docs/PRODUCTION-READINESS.md`](docs/PRODUCTION-READINESS.md)

---

## Typical MMM workflow

A normal model-to-decision path is

```text
1. register_dataset
2. inspect_dataset
3. validate_dataset
4. fit_mmm or submit_fit_mmm_job
5. diagnose_mmm
6. inspect descriptive posterior evidence
7. use decision-grade tools only when the gate permits them
8. retain dataset, model, configuration, package, and decision provenance
```

A useful agent should not skip directly from `fit_mmm` to a budget recommendation

### Example decision path

```text
fit_mmm
   |
   v
diagnose_mmm
   |
   +-- rejected/caution requiring stop --> explain evidence or request more measurement
   |
   +-- decision access permitted ------> simulate_budget / optimize_budget / optimize_flighting
```

---

## Typical CLV workflow

The CLV surface separates purchase behavior from monetary value instead of hiding both behind one generic prediction call

```text
1. fit_purchase_model
2. predict_expected_purchases / predict_probability_alive
3. fit_value_model when monetary modeling is required
4. predict_expected_spend
5. estimate_customer_lifetime_value
```

Legacy compatibility wrappers remain visible in the capability inventory as deprecated rather than pretending they are current first-choice APIs

---

## Architecture

The project is structured so the MCP transport does not own marketing or statistical behavior

```text
src/marketing_mcp/

MCP transport
  mcp/
    tools + resources + envelopes + request context
          |
          v
Application services
  services/
    datasets + modeling + diagnostics + decisions + plots + CLV + jobs
          |
          +--------------------+
          |                    |
          v                    v
Domain policy              Computation adapters
  domain/                    adapters/
    validation                PyMC-Marketing boundary
    diagnostics               PyMC / ArviZ integration
    decision rules
          |                    |
          +----------+---------+
                     |
                     v
Persistence + artifacts
  storage/ + repositories/ + jobs/ + credentials/

Cross-cutting boundaries
  security/       principals + scopes + tenant authorization + OAuth
  observability/  structured logs + metrics + traces
  http/           health + request safety + credential control API
  schemas/        typed public contracts
```

The main ownership rule is that orchestration may coordinate domain owners, but it should not duplicate their math, persistence semantics, or authorization rules

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the current and target topology

---

## Persistence and artifacts

The default local runtime uses SQLite-backed metadata, jobs, and credential state with local artifact storage

The repository also contains a shared-SQL persistence path used by the production-hardening work. Multi-instance production readiness must be judged against the current persistence and artifact evidence, not the existence of an adapter alone

Important local paths can be configured with environment variables including

```text
MARKETING_MCP_INGEST_DIR
MARKETING_MCP_ARTIFACT_DIR
MARKETING_MCP_METADATA_DB
MARKETING_MCP_MAX_DATASET_MB
MARKETING_MCP_PERSISTENCE_BACKEND
MARKETING_MCP_SHARED_SQL_URL
```

See `src/marketing_mcp/config.py` for the runtime configuration contract

---

## Security model

Remote access is request-scoped and tenant-aware

The security boundary includes

- authenticated principals propagated into MCP tool execution
- scope checks mapped to public tools
- object and tenant authorization
- backend-controlled API-key verification and revocation
- asymmetric OAuth verification for the production profile
- request safety middleware
- structured-log secret redaction
- fail-closed startup checks for insecure HTTP configurations

A valid token or API key does not imply access to every tenant or every operation

Read [`docs/SECURITY.md`](docs/SECURITY.md) for the full contract and known production gaps

---

## Observability

The runtime includes

- structured JSON logging
- secret scrubbing
- low-cardinality metrics
- trace context propagation
- liveness and readiness endpoints

Identifiers useful for correlation belong in logs or trace context where allowed, not in metric labels that create uncontrolled cardinality

Production exporters, alerts, and SLO evidence are tracked separately from the local observability implementation

---

## Capability maturity

Public capability status comes from `src/marketing_mcp/capabilities.py` and is rendered into [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md)

```text
stable        executable evidence is referenced for the capability
experimental  exposed, but the required evidence is incomplete or absent
deprecated    retained for compatibility and scheduled for removal
```

The registry, actual MCP discovery, generated documentation, and evidence references are checked for drift in tests

Do not hand-edit `docs/CAPABILITIES.md`

---

## Current maturity

**Advanced beta / release-candidate implementation, not release-approved**

The repository contains substantial hardening work across scientific correctness, recovery, remote security, observability, release evidence, agent quality, and upstream compatibility

That does not make every release gate green for the current commit

A gate is green only when machine-collected evidence for the exact commit being assessed proves the required property. Older test runs, historical release notes, a passing local command, or the existence of a test file are not substitutes for current release evidence

Current gate interpretation lives in [`docs/PRODUCTION-READINESS.md`](docs/PRODUCTION-READINESS.md)

---

## Planned next capability: Marketing Reconciliation Engine

The repository now has an implementation-ready plan for a bounded reconciliation capability

This is **planned work, not a current MCP runtime capability**

The v1 direction is intentionally narrow

- detect machine-checkable operational, data-integrity, and decision-safety incidents
- persist incident evidence and action attempts
- run shadow-first
- allow automatic mutation only for explicit low-risk internal recipes
- verify every repair before reporting an incident as healed
- escalate when evidence is uncertain
- keep commercial ad-platform mutation outside v1

The first planned automatic repair is subject-scoped expired worker-lease recovery. The plan explicitly rejects a free-form autonomous growth agent and arbitrary campaign actuation

Planning artifacts

- [Canonical product and technical plan](docs/plans/2026-09-12-0919-feat-marketing-reconciliation-engine-plan.md)
- [Staff Engineer execution brief](docs/plans/2026-09-12-0919-feat-marketing-reconciliation-engine-engineering-brief.md)
- [Atomic engineering task ledger](docs/plans/2026-09-12-0919-feat-marketing-reconciliation-engine-tasks.md)

Do not expose planned reconciliation tools or scopes as current capability until implementation, discovery, authorization, and evidence tests land together

---

## Verify the repository

Install the development dependencies first

```bash
uv sync --frozen --extra dev
```

### Fast and integration-oriented checks

```bash
uv run pytest -m "not statistical" -v
```

### Statistical checks

These run real PyMC-Marketing sampling and can take materially longer than ordinary unit tests

```bash
uv run pytest -m statistical -v
```

### Static checks

```bash
uv run ruff check src tests scripts
uv run pyright
```

### Documentation and capability drift

```bash
uv run python scripts/generate_capability_inventory.py --check
uv run python scripts/check_docs_drift.py
```

### Full suite and package build

```bash
uv run pytest -v
uv build
```

Passing these commands locally is useful engineering evidence. It is not by itself a production release approval

---

## Repository map

```text
.
├── src/marketing_mcp/
│   ├── adapters/       PyMC-Marketing computation boundary
│   ├── credentials/    API-key issuance, verifier storage, and revocation
│   ├── domain/         validation, diagnostics, allocation, and decision policy
│   ├── http/           health, request safety, and control-plane routes
│   ├── jobs/           durable jobs, idempotency, leases, fencing, worker CLI
│   ├── mcp/            tools, resources, envelopes, context, and task adapter
│   ├── observability/  structured logging, metrics, and tracing
│   ├── schemas/        typed public contracts
│   ├── security/       principals, scopes, authorization, OAuth, redaction
│   ├── services/       application workflows
│   └── storage/        SQLite migrations and durable stores
├── tests/
│   ├── contract/       public and decision-gate contracts
│   ├── integration/    transport, auth, persistence, resource, and worker behavior
│   ├── release/        G0-G5 and H0-H6 release assertions
│   ├── statistical/    real PyMC-Marketing statistical invariants
│   └── unit/           focused domain and service tests
├── docs/
│   ├── plans/          active implementation plans and engineering ledgers
│   ├── release-evidence/ machine-collected release proof
│   └── README.md       documentation truth map
├── scripts/            documentation, capability, release, and verification tooling
├── pyproject.toml      package and tool configuration
└── task_plan.md        broader implementation and phase tracker
```

---

## Documentation map

Start with the document that owns the question you are asking

| Question | Source of truth |
| --- | --- |
| What is publicly exposed | [`docs/CAPABILITIES.md`](docs/CAPABILITIES.md) |
| What does each tool promise | [`docs/TOOL-CONTRACTS.md`](docs/TOOL-CONTRACTS.md) |
| How is the code organized | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| When may model outputs drive decisions | [`docs/DECISION-INTEGRITY.md`](docs/DECISION-INTEGRITY.md) |
| What statistical rules are non-negotiable | [`docs/STATISTICAL-SAFETY.md`](docs/STATISTICAL-SAFETY.md) |
| How does authentication and tenancy work | [`docs/SECURITY.md`](docs/SECURITY.md) |
| What is actually release-ready | [`docs/PRODUCTION-READINESS.md`](docs/PRODUCTION-READINESS.md) |
| What evidence supports release claims | [`docs/release-evidence/`](docs/release-evidence/) |
| How should conflicting documentation be interpreted | [`docs/README.md`](docs/README.md) |
| What are engineers building next | [`docs/plans/`](docs/plans/) |

Plans are targets. Tests are evidence for the behavior they actually exercise. Release evidence is commit-specific. The current source and executable checks outrank historical prose

---

## Dependency policy

The supported package contract currently targets

```text
Python             >=3.12,<3.14
PyMC-Marketing     >=1.0.0,<2
MCP Python SDK     >=2,<3
Pydantic           >=2.12,<2.13
NumPy              >=2,<3
Pandas             >=2.2,<3
ArviZ              >=0.21,<2
```

The upstream canary can test newer dependency combinations without silently widening the committed package contract

PyMC-Marketing 2.x should be adopted only after adapter, statistical, plotting, optimization, calibration, and persisted-artifact compatibility is proven and any required migration is explicit

---

## Historical releases

Earlier v0.3 and v0.4 material remains in [`CHANGELOG.md`](CHANGELOG.md) and [`docs/FINAL-REVIEW.md`](docs/FINAL-REVIEW.md) for provenance

Historical release notes do not establish the readiness of the current commit

---

## License

Apache License 2.0. See [`LICENSE`](LICENSE)
