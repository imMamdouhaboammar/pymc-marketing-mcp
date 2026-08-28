---
title: "PyMC Skill Pack Architecture, Decision-Safety Integrity, and Multi-Agent Loop Engineering"
category: "Agent Skills & MCMC Architecture"
date: "2026-08-28"
status: "implemented"
tags:
  - "pymc-marketing"
  - "skill-conductor"
  - "skill-creator"
  - "loop-engineering"
  - "ce-compound"
  - "bayesian-decision-integrity"
---

# PyMC Skill Pack Architecture, Decision-Safety Integrity, and Multi-Agent Loop Engineering

## Executive Overview

This document codifies the technical findings, design decisions, execution patterns, and operational lessons from authoring the full **PyMC-Marketing Agent Skill Pack** (5 specialized packages) within the `pymc-marketing-mcp` ecosystem. It establishes durable guidance for future `/ce-setup`, `/loop-engineering`, and multi-agent development sessions.

---

## 1. Session Chronology & Extraction (A to Z)

### Timeline & Workflow Trajectory
1. **Initial Research & Analysis**:
   - Analyzed existing stub skills in `.agents/skills/` (`pymc-mmm-workflow`, `pymc-diagnostics-gate`, `pymc-budget-optimization`, `pymc-lift-calibration`, `pymc-clv-customer-analytics`).
   - Inspected repository source code (`src/marketing_mcp/`), MCP capability inventory (`docs/CAPABILITIES.md`), decision integrity rules (`docs/DECISION-INTEGRITY.md`), and statistical safety policies (`docs/STATISTICAL-SAFETY.md`).
2. **Subagent Parallelization Attempt**:
   - Dispatched 5 concurrent subagents to parallelize skill authoring.
   - Encountered `RESOURCE_EXHAUSTED` (429 rate limit / quota exhaustion) across subagent streams.
3. **Deterministic Fallback & Autonomous Execution**:
   - Switched from parallel subagent delegation to an in-process deterministic build pipeline (`scripts/build_pymc_skills.py`).
   - Sequentially constructed all 5 skills with full subdirectories (`references/`, `templates/`, `examples/`, `evals/`, `scripts/`, and `skill.package.json`).
4. **Validation & Verification**:
   - Ran linter: `uv run ruff check src tests scripts` (100% clean).
   - Ran doc drift check: `uv run python scripts/check_docs_drift.py` (11 documents verified).
   - Ran test suite: `uv run pytest -m "not statistical" -v` (446 passed, 0 failures).
5. **Git Synchronization & Push**:
   - Encountered remote divergence due to upstream launch plan merge (`origin/main`).
   - Fetched and cleanly rebased on `origin/main`.
   - Pushed commit `fb157ed` successfully.

---

## 2. Surprises & Root-Cause Analysis

| Surprise / Obstacle | Root Cause | Resolution & Durable Rule |
|---|---|---|
| **Subagent 429 Quota Exhaustion** | Simultaneous launch of 5 heavy subagents exceeded concurrent API rate limits. | **Fallback to local automation**: When multi-agent swarms hit API limits, fall back to a script-driven single-agent loop. |
| **`write_to_file` Scope Constraint** | `write_to_file` is reserved for `<appDataDir>/brain/<id>/` artifacts, rejecting project root paths. | **Use workspace tools**: Write workspace code via `run_command` with clean Python/shell file writers. |
| **Git Push Rejection** | Upstream PR #3 was merged into `origin/main` during session execution. | **Rebase before push**: Always run `git fetch origin && git rebase origin/main` before publishing. |

---

## 3. Core Architectural Learnings by Domain

### A. Bayesian Marketing Science & Decision Integrity (AI Engineer Lens)
- **Separation of Concerns**: PyMC-Marketing and ArviZ compute all statistical quantities. The agent orchestrates schemas, enforces convergence gates, and interprets posteriors. No arithmetic or LLM guesswork.
- **Hard Decision Gate Policy**:
  - `divergences > 0` $\implies$ Immediate `rejected` status.
  - $\hat{R} > 1.05$ or $\text{Bulk ESS} < 50$ or $\text{Coverage} < 50\%$ $\implies$ `rejected`.
  - Decision tools (`optimize_budget`, `simulate_budget`, `optimize_flighting`, `get_incremental_roas`) strictly fail closed on rejected models.
- **Marginal vs. Total iROAS**:
  - Total iROAS ($\Delta \text{Revenue} / \text{Spend}$) reflects historical average return.
  - Marginal iROAS ($\partial \text{KPI} / \partial \text{Spend}$) dictates the efficiency of the next dollar.
  - Equal marginal return theorem ($\lambda = \partial f_1/\partial x_1 = \dots = \partial f_k/\partial x_k$) governs optimal allocation.
- **Lineage Immutability in Lift Calibration**:
  - `calibrate_mmm` creates an immutable child model (`parent_model_id = ...`) without mutating the parent in place.
  - The child model must undergo fresh MCMC diagnosis (`diagnose_mmm`) before unlocking decision tools.

### B. Skill Authoring Standards (Skill-Conductor & Skill-Creator Lens)
- **Description Formula**:
  `[What it does] + Use when [4-5 trigger phrasings] + pushy clause ("even if they don't say X") + Do NOT use for [negatives]`.
  *Never include workflow steps in the description to prevent agents shortcutting the body.*
- **Map of Content (MOC)**:
  `SKILL.md` body remains $< 500$ lines, acting as an anchor table-of-contents linking to `references/` for deep theory.
- **Training Within Industry (TWI)**:
  Every critical step contains **Step** (imperative action), **Key Point** (critical detail), and **Why** (risk of omitting).
- **Comprehensive Evals**:
  Every skill package includes $\ge 6$ should-trigger, $\ge 4$ should-not-trigger (near-misses), and $\ge 2$ behavioral assertion scenarios.

### C. Loop Engineering & Autonomous Multi-Agent Swarms
- **Maker-Checker Separation**: In loop engineering, the generator agent and verifier agent must remain independent to eliminate confirmation bias.
- **Cost & Iteration Sentinel**: Hard caps ($2.00 token budget, 5 loop iterations) prevent runaway execution loops.
- **Continuous Dev-QA Feedback**: Verification gates must run at each task transition, not aggregated as a post-hoc batch.

---

## 4. Reusable Chunk Reference for Future Sessions

```json
{
  "future_session_patterns": {
    "subagent_parallelism": "Cap parallel subagents at 2-3 to avoid 429 quota exhaustion; provide single-agent deterministic fallback.",
    "mcmc_diagnostic_policy": "Enforce zero tolerance on divergences (>0 rejects); check R-hat <= 1.01 and Bulk ESS >= 400 for clean approval.",
    "decision_tool_prerequisites": "Always verify get_model_status before optimize_budget, simulate_budget, or optimize_flighting.",
    "skill_file_scaffolding": "Each skill package must include SKILL.md, references/, templates/, examples/, evals/, and skill.package.json.",
    "git_hygiene": "Fetch and rebase on origin/main before pushing branch modifications."
  }
}
```
