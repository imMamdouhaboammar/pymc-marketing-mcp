# Code Review & Architecture Guide

A practical, reproducible guide for navigating, reviewing, and debugging the `pymc-marketing-mcp` codebase and the Unified PyMC Marketing Platform.

---

## 1. System Topology & Architectural Invariants

### Monorepo & MCP Layer Division
```text
pymc-unified-platform-spec/
├── apps/gateway/                  # Rust Axum control plane (routing, auth, multi-tenant safety, events)
├── services/engine-api/           # Python ASGI internal service (preflight, dataset inspection)
├── services/analytics-worker/     # Python worker (PyMC MCMC sampling, artifact generation)
├── packages/contracts/            # Canonical Draft 2020-12 JSON schemas & Pydantic models
├── packages/storage/              # PostgreSQL DDL migrations & tenant-scoped repositories
└── pymc-marketing-mcp/            # Self-hostable, agent-native marketing science MCP runtime
    ├── src/marketing_mcp/
    │   ├── domain/                # Pure domain logic (priors, long_term, cohorts, portfolio, objectives)
    │   ├── schemas/               # Contract models and API schemas
    │   ├── storage/               # Metadata & artifact store
    │   └── tools/                 # Tool handlers registered to MCP protocol
    └── tests/
        ├── unit/                  # Fast, isolated unit tests (< 0.2s each, no MCMC sampling)
        ├── contract/              # Schema drift & capability inventory tests
        └── statistical/           # Real PyMC MCMC sampling tests (marked @pytest.mark.statistical)
```

### The 5 Core Invariants
1. **Zero Mathematical Reimplementation in Rust**: All statistical modeling (adstock, saturation, MCMC, CLV) stays 100% in Python. Rust is purely control plane.
2. **Multi-Tenant Scoping Mandatory**: Every database query and repository call MUST carry `organization_id`. Never query by primary key alone.
3. **Server-Side Diagnostic Decision Gates**: Downstream optimization or budget allocation is blocked if MCMC diagnostics (`max_rhat`, `divergences`, `min_bfmi`) fail policy thresholds.
4. **Epistemic Honesty in Naming**: Deterministic methods must never be labeled Bayesian (e.g. `DeterministicRidgeVARX` vs `BayesianVAR`). Uncertainty must be explicitly flagged if absent (`uncertainty_quantified=false`).
5. **Empirical Provenance Fidelity**: Confidence scores must never be fabricated from arbitrary magic constants. Confidence is derived from caller-supplied scores, experimental precision $1/(1+\text{SE})$, or explicit policy defaults.

---

## 2. Using `code-review-graph` for Instant Code Reviews

The MCP tool `code-review-graph` parses the codebase with Tree-sitter, maintains an incremental structural graph, and provides impact and flow analysis.

### Standard Review Workflow

#### Step 1: Update Graph
Re-parse any recently changed files incrementally:
```json
// Tool: code-review-graph:build_or_update_graph_tool
{
  "repo_root": "/path/to/pymc-marketing-mcp",
  "postprocess": "minimal"
}
```

#### Step 2: Analyze Impact Radius & Blast Radius
Determine which functions, classes, and downstream modules are affected by the diff:
```json
// Tool: code-review-graph:get_review_context_tool
{
  "base": "origin/main",
  "detail_level": "minimal"
}
```

#### Step 3: Trace Affected Execution Flows
Identify which MCP tools and user-facing workflows pass through changed nodes:
```json
// Tool: code-review-graph:get_affected_flows_tool
{
  "base": "origin/main",
  "detail_level": "minimal"
}
```

#### Step 4: Semantic Node Lookup & Debugging
To inspect any class, function, or flow when reviewing:
```json
// Tool: code-review-graph:semantic_search_nodes_tool
{
  "query": "PriorRecommendation",
  "limit": 5
}
```

---

## 3. Systematic Debugging Playbook (`code-review-graph:debug_issue`)

When a test fails or a review bot (e.g., Cubic, CodeRabbit) flags an issue:

1. **Locate Node & Callers**:
   - Use `code-review-graph` to inspect callers of the failing function:
   - Identify whether the bug is at the interface boundary or deep inside domain logic.
2. **Check Root Cause vs. Symptom (Ponytail Ladder)**:
   - Does this need to exist at all? (YAGNI)
   - Is it already solved in the codebase or standard library?
   - Fix the root cause in the shared domain module, not by patching individual callers.
3. **Reproduce via TDD**:
   - Write a minimal failing test in `tests/unit/` reproducing the exact failure mode.
   - Ensure the test asserts the specific exception (e.g. `pytest.raises(ValidationError)` instead of `Exception`).
4. **Implement Shortest Working Diff**:
   - Minimal code diff that solves the root cause.
   - Run linter and formatter: `uv run ruff check src tests scripts` and `uv run ruff format src tests scripts`.
   - Run type checking: `uv run pyright`.
5. **Verify No Downstream Drift**:
   - Run capability inventory: `uv run pytest tests/integration/test_capability_inventory.py`.
   - Run documentation drift check: `uv run pytest tests/unit/test_docs_drift.py`.

---

## 4. Verification Checklists & Commands

Run these checks before every commit or PR conclusion:

```bash
# 1. Fast Domain & Unit Tests
uv run pytest tests/unit/ -v

# 2. Code Quality & Formatting
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts

# 3. Static Type Analysis
uv run pyright

# 4. Capability & Documentation Drift
uv run pytest tests/integration/test_capability_inventory.py tests/unit/test_docs_drift.py -v

# 5. Full Platform Verification (from pymc-unified-platform-spec root)
./check.sh
```
