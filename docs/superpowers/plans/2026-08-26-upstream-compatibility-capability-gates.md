# Upstream Compatibility and Capability Gate Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent upstream PyMC-Marketing, PyMC, ArviZ, xarray or MCP SDK changes from silently altering production behavior, and require every new statistical capability to pass compatibility, scientific, security and agent-safety gates before becoming stable.

**Architecture:** Separate the locked production environment from declared supported ranges and latest-allowed canaries. Maintain explicit adapter compatibility contracts, run minimal real statistical flows against candidate dependency sets, and introduce a capability-admission template that forces upstream API evidence, invariants, decision-gate semantics, provenance, evals and rollback behavior before public exposure.

**Tech Stack:** uv lockfiles, GitHub Actions matrix, PyMC-Marketing 1.x, PyMC 6.x, ArviZ/xarray, MCP Python SDK v2, pytest statistical/integration suites.

**Spec:** `docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`

## Global Constraints

- Production runs an exact tested lock, not an unverified newest-compatible environment.
- Declared version ranges must be backed by compatibility evidence.
- A passing canary never widens dependency bounds automatically.
- Upstream API availability is not enough; behavioral/statistical semantics must be tested.
- New capabilities remain experimental until executable evidence covers their actual decision semantics.
- Capability expansion remains frozen until H0-H5 and G0-G5 are green.

---

### Task 1: Define supported-stack policy

**Files:**
- Modify: `docs/API-COMPATIBILITY.md`
- Create: `docs/engineering/DEPENDENCY-POLICY.md`
- Modify: `pyproject.toml` only after evidence supports any bound change

**Policy layers:**

```text
production lock      = exact uv.lock used for releases
supported range      = bounded versions tested in CI
latest-allowed canary = newest versions satisfying current bounds
pre-release watch    = optional non-blocking visibility
```

- [ ] Document the exact release lock and supported Python versions
- [ ] Document who/what is allowed to widen a bound
- [ ] Require release note + canary evidence for bound changes
- [ ] Add explicit MCP specification/SDK compatibility notes
- [ ] Commit

---

### Task 2: Create adapter compatibility contract tests

**Files:**
- Create: `tests/contract/test_pymc_marketing_api_contract.py`
- Create: `tests/contract/test_mcp_sdk_api_contract.py`
- Modify: `src/marketing_mcp/adapters/pymc_marketing.py` only when required

**PyMC-Marketing assertions:**

```text
MMM construction path exists
configured adstock/saturation constructors exist
fit/save/load paths return expected model/idata structures
budget optimizer path accepts expected dimensions/constraints
calibration path preserves lineage requirements
time-slice CV result shape is understood
CLV model classes used by adapter remain available
```

**MCP assertions:**

```text
server construction/discovery contract exists
streamable HTTP API used by project exists
auth verifier interfaces used by project exist
unsupported Tasks extension is not advertised
```

- [ ] Keep contract tests shape/semantic focused rather than snapshotting irrelevant internals
- [ ] Commit

---

### Task 3: Build latest-allowed compatibility canary

**Files:**
- Create/modify: `.github/workflows/upstream-canary.yml`
- Create/modify: `scripts/compatibility_canary.py`
- Create: `docs/release-evidence/canary/README.md`

**Canary sequence:**

```text
resolve newest allowed dependencies
record exact versions
run adapter contracts
run minimal real MMM fit/save/load
run one decision invariant
run one CLV real model flow
run MCP authenticated discovery/roundtrip
emit evidence artifact
```

- [ ] Do not reuse production lock in the latest-allowed lane
- [ ] Keep deterministic seed/tolerances explicit
- [ ] Fail visibly on xarray/ArviZ warning promoted to behavior-breaking error
- [ ] Commit

---

### Task 4: Add upstream warning/deprecation budget

**Files:**
- Create: `tests/contract/test_upstream_warnings.py`
- Modify: `docs/API-COMPATIBILITY.md`

- [ ] Maintain allowlisted upstream warnings with owner and expiration/review date
- [ ] Fail on new deprecation/future warnings in adapter-critical paths unless triaged
- [ ] Track known xarray/PyMC-Marketing changes before they become runtime failures
- [ ] Prohibit blanket warning suppression for statistical suites
- [ ] Commit

---

### Task 5: Define capability-admission document template

**Files:**
- Create: `docs/capabilities/CAPABILITY-ADMISSION-TEMPLATE.md`
- Modify: `docs/CAPABILITIES.md` generation metadata if useful

**Required fields:**

```text
business question
upstream primitive/API
why MCP should expose it
input contract
output/statistical quantity
uncertainty semantics
diagnostics/decision gate
extrapolation behavior
ownership/scope
provenance
statistical invariants
negative cases
agent route/skill changes
compatibility risk
rollback/downgrade path
executable evidence tests
```

- [ ] Require completed admission doc for every new public statistical tool
- [ ] Do not allow `stable` status in inventory until referenced tests exist
- [ ] Commit

---

### Task 6: Gate candidate Spend Reach support

**Files:**
- Create only after freeze lift: `docs/capabilities/spend-reach.md`
- Future modify: decision/adapters/tool files only after admission approval

**Investigation questions:**

- Does upstream spend-reach accounting close the incrementality window needed by current iROAS/simulation semantics?
- Should it be a new tool or an internal validation/warning in existing decision tools?
- What invariant proves the accounting is complete enough to claim a decision quantity?

**Required evidence before implementation:**

```text
real fitted model fixture
near-zero spend-change continuity
window accounting test
extrapolation behavior
provenance/uncertainty output contract
agent warning-preservation eval
```

- [ ] Keep capability experimental until evidence is complete

---

### Task 7: Gate sensitivity-analysis expansion

**Files:**
- Create only after freeze lift: `docs/capabilities/sensitivity-analysis.md`

**Required decisions:**

```text
use official upstream sensitivity primitives where available
distinguish prior sensitivity from spend-response sensitivity
avoid mixing model uncertainty with scenario uncertainty
make dimensions/channels name-safe
```

**Evidence:**

- transform-family real sampling test
- channel ranking stability/instability interpretation test
- dimension-safe result-shape test
- no fabricated certainty in agent evals

- [ ] Only promote `get_response_curves`/related capabilities after real behavioral evidence

---

### Task 8: Gate optimizer/flight planning alignment

**Files:**
- Create only after freeze lift: `docs/capabilities/optimizer-alignment.md`

**Required evidence:**

```text
budget conservation
constraint feasibility/infeasibility
carryover correctness
objective definition
marginal vs average return semantics
posterior uncertainty
extrapolation warnings
same result after save/load within tolerance
```

- [ ] Prefer upstream official optimizer primitives when they match the business contract
- [ ] Downgrade naming to heuristic if true optimization semantics cannot be proved

---

### Task 9: Add capability freeze/thaw automation

**Files:**
- Create: `src/marketing_mcp/capability_policy.py`
- Create: `tests/release/test_capability_freeze.py`
- Modify: capability inventory generator

**Interface:**

```python
def capability_work_allowed(readiness: ReadinessSnapshot) -> bool:
    required = {"G0", "G1", "G2", "G3", "G4", "G5", "AQG", "H0", "H1", "H2", "H3", "H4", "H5", "H6"}
    return all(readiness.is_green(gate) for gate in required)
```

- [ ] Fail release/CI when a new public capability appears while freeze is active unless explicitly marked internal/experimental investigation-only
- [ ] Exempt bug fixes and evidence work
- [ ] Commit

---

### Task 10: Establish H6 Upstream Compatibility gate

**Files:**
- Create: `tests/release/test_h6_upstream_compatibility.py`
- Modify: `docs/PRODUCTION-READINESS.md`

**Assertions:**

- exact production lock evidence exists
- adapter API contracts pass
- latest-allowed canary workflow exists and last required run is green for release candidates
- unsupported MCP extensions are not advertised
- known warning budget has no expired unresolved adapter-critical item
- supported dependency bounds match documented evidence
- every newly stable capability has an admission document and executable evidence

- [ ] Run H6 in release workflow
- [ ] Mark green only from CI evidence
- [ ] Commit

## Acceptance Criteria

This plan is complete when dependency upgrades cannot silently change statistical/protocol behavior and capability expansion follows a repeatable admission process rather than direct tool growth
