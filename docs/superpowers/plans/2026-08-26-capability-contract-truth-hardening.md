# Capability Contract Truth Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make runtime behavior, capability registry, generated documentation, agent routing, readiness, and release evidence describe the same product semantics with no stale or contradictory claims.

**Architecture:** Treat `src/marketing_mcp/capabilities.py` as the canonical public capability contract, but validate it against actual MCP discovery and behavioral evidence. Derive docs and agent skill guidance from the registry. Add contract tests for decision gates, evidence links, stable/experimental status, deprecations, readiness semantics, and skill-to-tool drift.

**Tech Stack:** Python 3.12, Pydantic, MCP discovery, pytest, generated Markdown, `.agents/skills`, existing capability registry and docs-drift scripts

**Spec:** `docs/PRODUCTION-READINESS.md`

## Global Constraints

- Stable capability status requires executable evidence
- A decision-gated runtime method must be marked gated in the capability contract
- Experimental capabilities must not be described as verified or release-critical
- Deprecated capabilities must remain explicit and have a replacement/migration path
- Generated docs are not manually edited to hide registry drift
- Agent skills may not instruct clients to call capabilities that the registry marks unavailable/deprecated without explicit compatibility intent
- Readiness must report dependency truth, not configured optimism

---

## Task 1: Fix the iROAS decision-gate drift

**Files:**
- Modify: `src/marketing_mcp/capabilities.py`
- Generate: `docs/CAPABILITIES.md`
- Test: `tests/unit/test_capability_decision_gates.py`

**Interfaces:**
- Consumes: `DecisionService.iroas()` runtime behavior
- Produces: truthful `get_incremental_roas` capability metadata

- [ ] **Step 1: Write a failing registry test**

Assert:

```python
cap = capability_by_name("get_incremental_roas")
assert cap.decision_gate is True
```

and verify runtime refuses an undiagnosed model with `MODEL_NOT_DIAGNOSED`.

- [ ] **Step 2: Correct the registry**

Mark `get_incremental_roas` as decision-gated because it calls `_approved()` before returning decision-grade iROAS.

- [ ] **Step 3: Regenerate capability documentation**

Run:

```bash
uv run python scripts/generate_capability_inventory.py
uv run python scripts/generate_capability_inventory.py --check
```

Expected: generated document records the decision gate as required

- [ ] **Step 4: Commit**

```bash
git add src/marketing_mcp/capabilities.py docs/CAPABILITIES.md tests/unit/test_capability_decision_gates.py
git commit -m "fix: align iROAS capability gate with runtime"
```

## Task 2: Validate every capability against real MCP discovery

**Files:**
- Modify: `tests/integration/test_capability_inventory.py`
- Create: `tests/contract/test_public_capability_contract.py`

**Interfaces:**
- Consumes: registry and MCP `list_tools`/`list_resources`
- Produces: exact registry-to-runtime set equality

- [ ] **Step 1: Assert exact tool-name equality**

The set of non-internal registered tool names must equal the names returned through an initialized MCP session.

- [ ] **Step 2: Assert exact resource-template equality**

The registry resource templates must equal the templates exposed by MCP discovery.

- [ ] **Step 3: Assert each public capability has a domain, status, summary, and delegate/evidence policy**

Stable capabilities require at least one evidence test reference. Experimental capabilities may have no evidence but must be labeled experimental.

- [ ] **Step 4: Assert no evidence test path is dead**

Resolve each referenced test path and test node. A renamed/deleted evidence test must fail the contract check.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_capability_inventory.py tests/contract/test_public_capability_contract.py
git commit -m "test: bind capability registry to MCP discovery"
```

## Task 3: Re-evaluate stable versus experimental capabilities

**Files:**
- Modify: `src/marketing_mcp/capabilities.py`
- Generate: `docs/CAPABILITIES.md`
- Modify: `docs/PRODUCTION-READINESS.md`
- Test: `tests/unit/test_capability_status_evidence.py`

**Interfaces:**
- Consumes: current evidence tests
- Produces: status labels based on executable evidence quality

- [ ] **Step 1: Define status admission rules in tests**

A tool may be `stable` only when it has:

```text
behavioral executable evidence
error-path evidence for release-critical tools
security/tenant evidence if it reads/writes tenant objects
real statistical evidence if it returns statistical outputs
```

- [ ] **Step 2: Reclassify async jobs if external-worker E2E is not yet green**

`submit_fit_mmm_job` must be `experimental` until API-process exit plus standalone-worker completion is proven.

- [ ] **Step 3: Keep resource templates experimental until resource-specific E2E evidence exists**

Resource authorization tests count only when executed through real MCP `read_resource`.

- [ ] **Step 4: Regenerate documentation and run drift checks**

Run:

```bash
uv run python scripts/generate_capability_inventory.py
uv run python scripts/generate_capability_inventory.py --check
uv run python scripts/check_docs_drift.py
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/marketing_mcp/capabilities.py docs/CAPABILITIES.md docs/PRODUCTION-READINESS.md tests/unit/test_capability_status_evidence.py
git commit -m "docs: make capability maturity evidence-driven"
```

## Task 4: Encode decision-tool invariants centrally

**Files:**
- Modify: `src/marketing_mcp/capabilities.py`
- Modify: `src/marketing_mcp/security/policy.py`
- Create: `src/marketing_mcp/domain/decisions/policy.py`
- Test: `tests/contract/test_decision_capability_policy.py`

**Interfaces:**
- Consumes: capability name
- Produces: scope requirement and diagnostics-gate requirement from one policy source

- [ ] **Step 1: Write policy consistency tests**

For each decision-grade capability, assert both:

```text
required scope includes marketing:decide
decision gate is required where model diagnostics are prerequisite
```

- [ ] **Step 2: Define canonical decision-grade capability set**

At minimum review:

```text
get_incremental_roas
simulate_budget
optimize_budget
optimize_flighting
```

Do not automatically gate descriptive tools that intentionally expose rejected-model evidence.

- [ ] **Step 3: Make tool registration/tests consume the policy**

Avoid separate hand-maintained lists that can drift independently.

- [ ] **Step 4: Commit**

```bash
git add src/marketing_mcp/capabilities.py src/marketing_mcp/security/policy.py src/marketing_mcp/domain/decisions/policy.py tests/contract/test_decision_capability_policy.py
git commit -m "refactor: centralize decision capability policy"
```

## Task 5: Make readiness claims machine-derived

**Files:**
- Modify: `scripts/render_production_readiness.py`
- Modify: `scripts/collect_release_evidence.py`
- Modify: `docs/PRODUCTION-READINESS.md`
- Test: `tests/release/test_readiness_claim_derivation.py`

**Interfaces:**
- Consumes: release evidence JSON and gate definitions
- Produces: human-readable readiness status that cannot exceed evidence

- [ ] **Step 1: Write a failing stale-evidence test**

If evidence commit SHA differs from the current target SHA, the rendered gate must be `evidence pending`, not green.

- [ ] **Step 2: Define machine-readable gate evidence schema**

Every gate record must contain:

```json
{
  "gate": "H1",
  "commit_sha": "40-hex-sha",
  "status": "pass",
  "commands": ["non-empty"],
  "artifacts": ["non-empty for artifact-producing gates"]
}
```

- [ ] **Step 3: Render status from evidence only**

Manual prose may explain limitations, but the status field must come from machine evidence.

- [ ] **Step 4: Commit**

```bash
git add scripts/render_production_readiness.py scripts/collect_release_evidence.py docs/PRODUCTION-READINESS.md tests/release/test_readiness_claim_derivation.py
git commit -m "fix: derive readiness status from exact-commit evidence"
```

## Task 6: Harden agent skill capability guidance against drift

**Files:**
- Modify: `.agents/skills/pymc-mmm-workflow/SKILL.md`
- Modify: `.agents/skills/pymc-budget-optimization/SKILL.md`
- Modify: `.agents/skills/pymc-diagnostics-gate/SKILL.md`
- Modify: `.agents/skills/pymc-clv-customer-analytics/SKILL.md`
- Modify: `.agents/skills/pymc-lift-calibration/SKILL.md`
- Create: `scripts/check_agent_skill_capability_drift.py`
- Create: `tests/evals/test_agent_skill_capability_truth.py`

**Interfaces:**
- Consumes: canonical capability registry and the five installed repository skills
- Produces: skill guidance that references only valid capability names and preserves maturity/decision-gate rules

- [ ] **Step 1: Write the drift checker test first**

Create fixtures containing a valid tool name, a removed tool name, a deprecated tool used without compatibility context, and an experimental tool described as stable. The checker must accept the valid case and reject the three invalid cases.

- [ ] **Step 2: Implement `check_agent_skill_capability_drift.py`**

The script must load the canonical registry, scan all `.agents/skills/*/SKILL.md` files for MCP tool/resource references, and fail when it finds:

```text
unknown capability name
deprecated capability presented as the preferred route
experimental capability described as stable/verified
decision-gated capability guidance that omits diagnostics prerequisite where the skill prescribes the workflow
```

- [ ] **Step 3: Correct each skill against the registry**

For the MMM, budget, diagnostics, CLV, and lift-calibration skills, ensure every named tool exists and that decision-grade sequences preserve diagnostics and warning rules.

- [ ] **Step 4: Add negative workflow eval cases**

`tests/evals/test_agent_skill_capability_truth.py` must cover:

```text
undiagnosed model -> optimization guidance requires diagnose_mmm first
diagnosed rejected model -> no decision-grade recommendation
unsupported capability request -> no invented tool
experimental capability -> experimental warning is preserved
deprecated CLV wrapper -> supported replacement is preferred
```

- [ ] **Step 5: Run drift and eval verification**

Run:

```bash
uv run python scripts/check_agent_skill_capability_drift.py
uv run pytest tests/evals/test_agent_skill_capability_truth.py -q
uv run pytest tests/evals -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .agents/skills scripts/check_agent_skill_capability_drift.py tests/evals/test_agent_skill_capability_truth.py
git commit -m "test: bind agent skills to capability truth"
```

## Task 7: Enforce deprecation contracts

**Files:**
- Modify: `src/marketing_mcp/capabilities.py`
- Generate: `docs/CAPABILITIES.md`
- Test: `tests/contract/test_deprecation_contract.py`

**Interfaces:**
- Consumes: deprecated capability metadata
- Produces: explicit replacement and removal policy

- [ ] **Step 1: Require replacement metadata for deprecated tools**

Current deprecated CLV compatibility tools must identify their replacement capability where one exists.

- [ ] **Step 2: Test deprecated response guidance**

Deprecated tool invocations must remain compatible during the announced window and include non-breaking migration guidance in metadata/docs.

- [ ] **Step 3: Commit**

```bash
git add src/marketing_mcp/capabilities.py docs/CAPABILITIES.md tests/contract/test_deprecation_contract.py
git commit -m "docs: formalize capability deprecation contracts"
```

## Acceptance criteria

This plan is complete when:

- `get_incremental_roas` contract matches its actual diagnostics gate
- registry tool/resource sets equal real MCP discovery
- every stable capability points to live executable evidence
- statistical stable tools reference real statistical evidence
- async job stability reflects external-worker evidence, not local async execution
- decision-grade scope/gate rules are centrally consistent
- readiness status cannot be green on stale or mismatched evidence
- all five installed agent skills pass capability drift verification
- agent skill guidance cannot invent or prefer unavailable/deprecated capabilities
- deprecated capabilities have explicit migration metadata
- `generate_capability_inventory.py --check`, docs drift, contract tests, integration tests, skill drift checks, and evals all pass
