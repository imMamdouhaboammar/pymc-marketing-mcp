# Production Readiness Gates

Source of truth for release status. Gate definitions are copied from
`docs/superpowers/specs/2026-08-23-production-grade-stabilization.md`.

A gate may be marked green only from executable evidence produced at the commit being assessed.
Manually asserted pass/fail claims are not evidence.

## Status

| Gate | Name | Status | Evidence |
|---|---|---|---|
| G0 | Baseline Truth | green | `tests/release/test_g0_production_truth.py` |
| G1 | Scientific Correctness | not started | — |
| G2 | Service Recovery | not started | — |
| G3 | Remote Security | not started | — |
| G4 | Operability | not started | — |
| G5 | Release Evidence | not started | — |
| AQG | Agent Quality Gate | not started | — |

Current maturity: **M1 partial** (advanced beta). Target for `0.5.0` is M3 minimum with M4 CI and
observability foundations.

## Gate G0 - Baseline Truth

Must pass before feature work continues.

- package version, health endpoint version, docs, and image tag agree
- all public tools appear in generated inventory
- every public tool has a documented contract
- v0.4 tests are executed and recorded from current HEAD
- no documentation claims a completed behavior without a linked test

## Gate G1 - Scientific Correctness

- channel-specific configuration changes actual model construction
- model comparison honors `loo`, `waic`, `stacking`, and `all` semantics
- CLV APIs are model-specific and real-fit tested
- dynamic flighting behavior is truthful and budget-conserving
- plot calculations use statistically correct dimensions
- all decision tools retain diagnostics gating

## Gate G2 - Service Recovery

- model/job state survives process restart
- artifact and metadata references remain consistent
- duplicate submissions can be detected
- cancellation and failure state are persisted
- backup and restore are tested

## Gate G3 - Remote Security

- production HTTP refuses startup without configured auth
- token-in-query is rejected
- scopes are enforced per tool group
- secrets are redacted in logs and errors
- unauthorized cross-principal access is rejected

## Gate G4 - Operability

- logs, metrics, and traces include request and job correlation IDs
- readiness reflects dependency health
- sampling failures are observable
- alertable error-rate and queue-depth metrics exist
- operator runbook covers the top failure modes

## Gate G5 - Release Evidence

- PR pipeline green
- nightly statistical suite green
- package and image built from the same commit
- clean install smoke test passes
- dependency canary is green or explicitly waived with documented evidence
- release evidence file is generated from CI

## Agent Quality Gate

- every skill capability maps to a current tool contract
- evals run rather than contain pre-marked pass values
- negative scenarios protect diagnostics and causal claims
- tool trace assertions prove behavior

## Release Rule

No `0.5.0` release until G0 through G5 plus the Agent Quality Gate are green from current-head CI
evidence. No `1.0.0` release until the M5 Decision-Grade gate in
`docs/superpowers/plans/2026-08-23-decision-governance-audit.md` is also green.
