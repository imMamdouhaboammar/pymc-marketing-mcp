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
4. Its MCP resource summary listed only **6 of 14** current resources. The omitted entries were the 8 scientific-skill resources under `marketing://skills...`.
5. `scripts/check_docs_drift.py` checks 11 current-state documents for release versions, tool headings, transform vocabulary, CLI transport names, and decision-gate markers. It does not currently assert resource-summary completeness or prevent copied capability totals from becoming stale.
6. `docs/README.md` defines a truth hierarchy, but it did not explicitly map each volatile fact to one canonical owner or define when copied values are acceptable.

## Changes in this PR

- Remove the fixed capability count from the root README and point readers to the generated inventory for totals, maturity, and evidence.
- Expand the README's representative capability map to include recovery/resume, artifact exchange, agent evidence, and scientific skill guidance.
- Add an SSOT ownership matrix and copied-fact rule to `docs/README.md`.
- Make the MCP resource section of `docs/TOOL-CONTRACTS.md` enumerate all resources in the current generated inventory.
- Keep runtime behavior, schemas, capability maturity, security policy, and release-gate status unchanged.

## Upstream terminology checks

Primary upstream documentation was consulted for terminology only:

- PyMC-Marketing official documentation/repository: MMM calibration with experiments/lift evidence, Bayesian MMM, and budget allocation remain library-owned statistical concepts. Project docs should describe the MCP boundary without implying that the agent computes those quantities itself.
- Model Context Protocol Python SDK official documentation/repository: tools and resources are separate MCP primitives, and `stdio` / `streamable-http` are official transport terms. This repository must still document only the transports its own CLI enables.

Upstream capability does not override this repository's source, schemas, policies, or release evidence.

## Follow-up audit, intentionally not claimed complete here

The next documentation pass should verify each claim against current source before editing:

1. `AGENTS.md`: reconcile job-execution, persistence, FastMCP/MCP-SDK, deployment, and native-acceleration statements with current runtime code and exact evidence.
2. `docs/PRODUCTION-READINESS.md`: compare every gate status with the newest exact-commit evidence; do not promote a gate from prose.
3. `docs/SECURITY.md`: verify current authentication profiles, tenant/object authorization, anonymous-beta behavior, and remote-resource enforcement.
4. `docs/DEPLOYMENT-GCP.md`: verify Cloud Run, GCS/FUSE, worker topology, health endpoints, and credential assumptions against current scripts/configuration.
5. `docs/API-COMPATIBILITY.md`: verify dependency ranges against `pyproject.toml` and current upstream compatibility tests.
6. Historical plans, findings, and release notes: ensure they are explicitly labeled historical/target where they can otherwise be mistaken for current behavior.
7. Failure lessons and agent guidance: ensure canonical indexes and pointers remain complete instead of duplicating operational truth in multiple places.

## Proposed guardrail follow-up

A separate code/test PR can extend documentation drift checks to cover:

- every generated MCP resource being represented in the public contract document
- accidental reintroduction of a hard-coded capability total in overview docs
- optionally, explicit machine-readable SSOT markers for version, transport, decision-gate, and resource-owner claims

That guardrail should be implemented with tests rather than relying on prose conventions alone.

## Acceptance criteria for this PR

- [x] README no longer hard-codes the stale capability total
- [x] README links capability totals and maturity to the generated inventory
- [x] `docs/README.md` identifies canonical owners for volatile documentation facts
- [x] `docs/TOOL-CONTRACTS.md` represents all 14 current MCP resources
- [x] No runtime or statistical behavior is changed
- [ ] `uv run python scripts/generate_capability_inventory.py --check`
- [ ] `uv run python scripts/check_docs_drift.py`
- [ ] `uv run pytest tests/unit/test_docs_drift.py tests/release/test_g0_production_truth.py -v`

The unchecked verification items should be satisfied by repository CI or an exact checkout before merge.
