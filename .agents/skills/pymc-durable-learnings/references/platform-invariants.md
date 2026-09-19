# PyMC Unified Marketing Platform: Platform Invariants & System Directory

This reference document outlines the architectural boundaries, existing platform rules, verification suites, and persistent state files for the Unified PyMC Marketing Platform.

---

## 1. Monorepo Topology

```text
pymc-unified-platform-spec/
├── apps/
│   ├── gateway/                  # Rust (Axum 0.8 + Tokio) control plane API
│   └── web/                      # React 19 + TypeScript + Vite UI
├── services/
│   ├── engine-api/               # Python ASGI internal service for preflight & inspection
│   └── analytics-worker/         # Python async compute worker (MCMC sampling & trace serialization)
├── packages/
│   ├── contracts/                # Canonical Draft 2020-12 JSON schemas & Pydantic models
│   ├── storage/                  # PostgreSQL DDL migrations & tenant-scoped repositories
│   ├── rust/platform-contracts/  # Rust Serde contract crate
│   ├── ts-client/                # TypeScript API client & type definitions
│   └── python/marketing_core/    # Linked PyMC-Marketing scientific core
├── migration/baselines/          # Golden datasets, snapshots, and diagnostic gate manifests
├── Failure-lessons/              # Durable engineering post-mortems (Lessons 01..64+)
├── tasks.md                      # Master 88-task migration tracker (UP-001..UP-088)
├── state.toon                    # TOON v4.1 runtime verification ledger and platform state
├── sync_upstream.sh              # Upstream PyMC MCP synchronization script
└── check.sh                      # Full platform verification runner
```

---

## 2. Core Operating Invariants

1. **Zero Mathematical Reimplementation in Rust (`INV2`)**:
   - PyMC, PyTensor, ArviZ, MCMC sampling, and Bayesian statistical logic remain 100% in Python (`packages/python/marketing_core` / `pymc-marketing-mcp`).
   - Rust (`apps/gateway`) is strictly for HTTP routing, authentication, multi-tenant safety, outbox dispatch, and diagnostic decision gate evaluation.

2. **Mandatory Multi-Tenant Scoping (`INV3`)**:
   - Every database query and repository operation MUST carry `organization_id`.
   - Never fetch, mutate, or delete an object (Project, Dataset, ModelSpec, Run, Artifact) by primary key alone.
   - Enforce cross-tenant isolation and verify against `tests/security/test_cross_tenant_security.py`.

3. **Server-Side Diagnostic Decision Gates (`INV4`)**:
   - MCMC diagnostics (`max_rhat <= 1.05`, `divergences == 0`, `min_bfmi >= 0.2`) govern downstream optimization and artifact generation.
   - Downstream budget allocation and scenario planners fail closed if a run is blocked by diagnostic policy.

4. **Runtime & Package Manager Discipline (`INV5`, `INV6`)**:
   - **JavaScript / TypeScript**: **Bun is mandatory** (`bun install`, `bun run build`, `bun test`). npm and yarn are strictly prohibited.
   - **Rust**: Cargo 1.97+ / Rust 2024 edition.
   - **Python**: Python 3.12 with `.venv` / `uv`. (Homebrew Python 3.14 breaks pytensor/pandas).
   - **Colima is prohibited** due to excessive resource footprint; use native binaries.

---

## 3. Standard Verification Commands

| Scope | Command | Purpose |
|---|---|---|
| **Full Platform** | `./check.sh` | Runs sync, Rust workspace, TS client, Python contracts & storage |
| **Upstream Sync** | `./sync_upstream.sh` | Pulls upstream diffs and checks schema compatibility |
| **Rust Control Plane** | `cargo test --workspace` | Tests Axum routes, tenants, outbox dispatch |
| **TypeScript Client** | `bun --filter @pymc/ts-client test` | Validates generated API types and requests |
| **Web Dashboard** | `cd PyMC-Dashboard-Adapter && bun x vite build` | Verifies React 19 UI build |
| **Python Contracts** | `PYTHONPATH=pymc-marketing-mcp/src:. .venv/bin/pytest pymc-marketing-mcp/tests/contract/ -q` | MCP contract snapshots |
| **Platform Storage & Security** | `PYTHONPATH=. .venv/bin/pytest packages/contracts/tests/ packages/storage/tests/ services/ tests/security/ -q` | Multi-tenant isolation & repositories |

---

## 4. `state.toon` Ledger Fields to Maintain

When documenting a new lesson or invariant:
- **`failure_lessons_count`**: Bump to current total count (e.g. `65`).
- **`operating_invariants`**: If the lesson creates a fundamental platform invariant, register it in the `operating_invariants` array.
- **`session_handoff`**: Update `failure_lessons_count` under `session_handoff`.

---

## 5. Agent Memory Integration Protocols

- **`gbrain` MCP Tool**:
  - `remember`: Save concise summary: `"Learned failure class [CLASS]: [INVARIANT]"`.
  - `extract_facts`: Register facts regarding the root cause, subsystem, and regression test.
  - `add_timeline_entry`: Log the completion of the durable lesson.
- **Compound Engineering (`ce-compound`)**:
  - If appropriate, cross-pollinate with `docs/solutions/<category>/<slug>.md` for broader engineering discoverability.
