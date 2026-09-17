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

## Current-state documents

- `PRODUCTION-READINESS.md`: current release status, gate evidence and blockers
- `ARCHITECTURE.md`: architecture implemented today plus the target production topology
- `SECURITY.md`: controls implemented today, known gaps and target security properties
- `API-COMPATIBILITY.md`: declared dependency ranges and how compatibility is proven
- `TOOL-CONTRACTS.md`: public MCP tool/resource contracts and maturity notes
- `CAPABILITIES.md`: generated public capability inventory
- `SCIENTIFIC-SKILLS.md`: generated Skill delivery architecture and complete capability-to-Skill coverage matrix
- `DECISION-INTEGRITY.md`: decision gate semantics and statistical decision policy
- `STATISTICAL-SAFETY.md`: non-negotiable statistical safety rules
- `STATISTICAL-TESTING.md`: statistical test methodology and evidence rules
- `VERIFICATION-MATRIX.md`: coverage map showing what is implemented, partially evidenced or still blocked
- `DEPLOYMENT-GCP.md`: current deployment status and target Google Cloud topology

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
