# Documentation Map and Truth Model

This directory separates current verified behavior, current implementation with known hardening gaps, target architecture, and historical records

## Truth hierarchy

When documents disagree, use this order

1. Current source code and executable tests
2. `src/marketing_mcp/capabilities.py` for the public MCP capability surface
3. Machine-collected current-commit evidence under `docs/release-evidence/`
4. `docs/PRODUCTION-READINESS.md` for gate interpretation
5. Current architecture, security, compatibility, statistical, and tool-contract documents
6. Hardening plans under `docs/superpowers/plans/`
7. Historical release notes and review snapshots

A test file existing in the repository is not enough to mark a release gate green. A green gate requires evidence produced for the exact commit being assessed, according to `docs/release-evidence/README.md`


## SSOT ownership matrix

Use pointers to the canonical owner for volatile facts instead of copying values into multiple documents

| Fact | Canonical owner | Derived or interpretive docs | Rule |
| --- | --- | --- | --- |
| Public capability names, kind, maturity, decision-gate flag, evidence references | `src/marketing_mcp/capabilities.py` | generated `docs/CAPABILITIES.md`, README summaries | Regenerate the inventory; avoid hand-copying totals into overview prose |
| Public tool and resource semantics | MCP registrations, schemas, application services, domain policy | `docs/TOOL-CONTRACTS.md` | Contracts may explain behavior, but names must stay aligned with the generated inventory |
| Package version and dependency ranges | `pyproject.toml` plus the runtime package version | README, `docs/API-COMPATIBILITY.md` | Do not promote an unsupported version from historical prose |
| Decision-gated operations and diagnostic policy | capability registry plus `src/marketing_mcp/domain/diagnostics/` | `docs/DECISION-INTEGRITY.md`, `docs/STATISTICAL-SAFETY.md` | A prose change cannot relax a runtime gate |
| Supported CLI transports | CLI/runtime source | README and deployment docs | Document only accepted runtime values; upstream SDK capabilities are not automatically enabled here |
| Release readiness | exact-commit machine evidence under `docs/release-evidence/` | `docs/PRODUCTION-READINESS.md` | Status prose interprets evidence; it does not create evidence |
| Deployment and security behavior | runtime configuration, middleware, authorization, persistence and deployment code | `docs/DEPLOYMENT-GCP.md`, `docs/SECURITY.md` | Current behavior and target architecture must be labeled separately |

### Copied-fact rule

High-churn values such as capability totals, evidence counts, release-gate status, supported versions, and generated resource inventories should normally be linked to their canonical owner rather than repeated in overview documents. If a copied value is necessary for readability, it must be covered by an executable drift check or updated in the same change as its owner

## Current-state documents

- `PRODUCTION-READINESS.md`: current release status, gate evidence and blockers
- `ARCHITECTURE.md`: architecture implemented today plus the target production topology
- `NATIVE-INTERACTION-RUNTIME-AUDIT.md`: traced MCP hot paths and verified/native/planned ownership
- `SECURITY.md`: controls implemented today, known gaps and target security properties
- `API-COMPATIBILITY.md`: declared dependency ranges and how compatibility is proven
- `TOOL-CONTRACTS.md`: public MCP tool/resource contracts and maturity notes
- `CAPABILITIES.md`: generated public capability inventory
- `DECISION-INTEGRITY.md`: decision gate semantics and statistical decision policy
- `STATISTICAL-SAFETY.md`: non-negotiable statistical safety rules
- `STATISTICAL-TESTING.md`: statistical test methodology and evidence rules
- `VERIFICATION-MATRIX.md`: coverage map showing what is implemented, partially evidenced or still blocked
- `DEPLOYMENT-GCP.md`: current deployment status and target Google Cloud topology
- `OPERATIONS.md`: single-instance runbook (deploy, health checks, alerts, key rotation, backup/restore, incidents)

## Planning documents

`docs/superpowers/plans/README.md` is the entry point for the production stabilization and 2026-08-26 hardening amendment

Plans describe target work. They are not evidence that a target behavior already exists

## Release evidence

`docs/release-evidence/` contains the only artifacts that may support a current-commit release claim

The historical `v0.4-current-head.md` baseline is useful for comparison but is not evidence for later commits

## Historical documents

`FINAL-REVIEW.md` is a historical snapshot of the earlier v0.3 review and is not current production-readiness evidence

Older findings and release sections should be read only in their stated historical scope

## Status vocabulary

- `verified`: implemented and supported by executable evidence for the exact claim
- `implemented`: code exists, but the broader production property has not been proven end to end
- `partial`: part of the target property exists, with named gaps still open
- `blocked`: a required dependency or evidence path is absent
- `historical`: retained for provenance only
- `target`: planned state, not current behavior

## Documentation change rule

Any change that affects a public tool, decision gate, security boundary, deployment topology, persistence contract, supported dependency range or release gate must update the relevant current-state document in the same change

Run before presenting documentation as current

```bash
uv run python scripts/generate_capability_inventory.py
uv run python scripts/check_docs_drift.py
uv run pytest tests/unit/test_docs_drift.py tests/release/test_g0_production_truth.py -v
```
