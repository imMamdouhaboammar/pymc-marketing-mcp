# Documentation SSOT Refresh Plan

Date: 2026-09-20
Scope: documentation-only correction and follow-up audit plan
Repository: `imMamdouhaboammar/pymc-marketing-mcp`

## Why this change exists

The repository already has a documentation truth hierarchy, generated capability inventory, and drift checks. The current overview layer still contains copied facts that can age independently from their canonical owners, and the resource contract summary is incomplete.

This plan treats documentation as a product surface. It separates facts verified from the current repository from follow-up items that still need source-level validation.

## Verified findings at branch cut

1. `docs/CAPABILITIES.md` is generated from `src/marketing_mcp/capabilities.py` and currently lists **64 capabilities: 50 tools and 14 resources**.
2. The root README still copied an older total of **39 capabilities**, so the overview disagreed with the generated inventory even though the inventory itself is current.
3. `docs/TOOL-CONTRACTS.md` has headings for all **50 public tools** in the generated inventory.
4. Its MCP resource summary listed only **6 of 14** current resources. The omitted entries were the 8 scientific-skill resources under `marketing://skills...`. Additionally, all 14 resources were previously grouped as "resource templates", whereas runtime discovery separates 8 parameterized resource templates (`list_resource_templates()`) from 6 static resources (`list_resources()`), and `marketing://models/{model_id}/lineage` returns a single model record with direct `parent_model_id` provenance rather than a traversed lineage chain.
5. `scripts/check_docs_drift.py` checks 11 current-state documents for release versions, tool headings, transform vocabulary, CLI transport names, and decision-gate markers. It does not currently assert resource-summary completeness or prevent copied capability totals from becoming stale.
6. `docs/README.md` defines a truth hierarchy, but it did not explicitly map each volatile fact to one canonical owner or define when copied values are acceptable.

## Changes in this PR

- Remove the fixed capability count from the root README and point readers to the generated inventory for totals, maturity, and evidence.
- Expand the README's representative capability map to include recovery/resume, artifact exchange, agent evidence, and scientific skill guidance.
- Add an SSOT ownership matrix and copied-fact rule to `docs/README.md`.
- Partition the MCP resource section of `docs/TOOL-CONTRACTS.md` into 8 parameterized resource templates and 6 static resources according to MCP discovery primitives.
- Align `marketing://models/{model_id}/lineage` contract and capability registry descriptions with runtime reality (single model record with direct `parent_model_id` provenance, no traversed chain).
- Keep runtime behavior, schemas, capability maturity, security policy, and release-gate status unchanged.

## Upstream terminology checks

Primary upstream documentation was consulted for terminology only:

- PyMC-Marketing official documentation/repository: MMM calibration with experiments/lift evidence, Bayesian MMM, and budget allocation remain library-owned statistical concepts. Project docs should describe the MCP boundary without implying that the agent computes those quantities itself.
- Model Context Protocol Python SDK official documentation/repository: tools and resources are separate MCP primitives, and `stdio` / `streamable-http` are official transport terms. This repository must still document only the transports its own CLI enables.

Upstream capability does not override this repository's source, schemas, policies, or release evidence.

## Completed audit & remediations

The comprehensive follow-up documentation audit verified each claim against source and implemented the following remediations:

1. `AGENTS.md`: reconciled jobs and worker execution (`AsyncioJobExecutor` and `ProcessJobWorker`), MCP Python SDK (`MCPServer`) async context decoupling, and native acceleration pillars (clarified that Python owns 100% of MCMC convergence and decision gating per Failure Lesson 28, while Rust owns request framing and admission). Replaced partial 14-lesson list with canonical link to `Failure-lessons/README.md` (64 codified post-mortems). Added `AGENTS.md` to `DOCUMENTED_DOCS` for continuous drift enforcement.
2. `docs/PRODUCTION-READINESS.md`: audited gate status claims against commit evidence; maintained truthful advanced beta / release-candidate status.
3. `docs/SECURITY.md`: clarified anonymous HTTP public beta posture (`MARKETING_MCP_ALLOW_ANONYMOUS_HTTP=true`) and fail-closed binding behavior.
4. `docs/DEPLOYMENT-GCP.md`: verified staging/development boundaries for Cloud Run and storage configurations.
5. `docs/API-COMPATIBILITY.md` & `docs/ARCHITECTURE.md`: aligned `pymc-marketing` declared range to `>=1.1.0,<2` and added `httpx>=0.27,<1` to match `pyproject.toml`.
6. Decision gate alignment: marked `get_incremental_roas` as `decision_gate_required=True` in `src/marketing_mcp/capabilities.py`, regenerated `docs/CAPABILITIES.md`, and updated `docs/DECISION-INTEGRITY.md` drift-check marker to match runtime enforcement in `DecisionService.iroas()`.
7. Executable dependency drift check: implemented `check_dependency_ranges` in `src/marketing_mcp/docs_drift.py` and unit tests in `tests/unit/test_docs_drift.py` to prevent declared dependency tables from diverging from `pyproject.toml`.

## Implemented guardrails

1. `check_resource_contracts` in `src/marketing_mcp/docs_drift.py` verifying every canonical MCP resource template and static resource is documented in `docs/TOOL-CONTRACTS.md`.
2. `check_dependency_ranges` in `src/marketing_mcp/docs_drift.py` asserting table rows in `docs/API-COMPATIBILITY.md` match `pyproject.toml` declared dependencies.
3. `AGENTS.md` included in `DOCUMENTED_DOCS` to prevent version, tool, and transport drift in contributor guides.
4. `test_all_decision_tools_declared_gated_in_capability_registry` in `tests/contract/test_decision_gate_contract.py` asserting all runtime-gated decision tools are marked in the capability registry.

## Acceptance criteria for this PR

- [x] README no longer hard-codes the stale capability total
- [x] README links capability totals and maturity to the generated inventory
- [x] `docs/README.md` identifies canonical owners for volatile documentation facts
- [x] `docs/TOOL-CONTRACTS.md` represents all 14 current MCP resources partitioned into templates and static resources
- [x] `marketing://models/{model_id}/lineage` accurately documented as single-record direct provenance
- [x] `get_incremental_roas` decision gate aligned across runtime, capability registry, generated inventory, and drift checks
- [x] `AGENTS.md` reconciled with current runtime (workers, MCP SDK, native acceleration boundaries, failure lessons)
- [x] `docs/API-COMPATIBILITY.md` and `docs/ARCHITECTURE.md` dependency ranges aligned with `pyproject.toml`
- [x] `docs/SECURITY.md` documents anonymous HTTP beta posture and fail-closed public interface binding
- [x] Executable resource-contract and dependency drift checks implemented and verified
- [x] No runtime or statistical behavior is changed
- [x] `uv run python scripts/generate_capability_inventory.py --check`
- [x] `uv run python scripts/check_docs_drift.py`
- [x] `uv run pytest tests/unit/test_docs_drift.py tests/release/test_g0_production_truth.py tests/contract/test_decision_gate_contract.py -v`

All verification items verified and passing on this branch.
