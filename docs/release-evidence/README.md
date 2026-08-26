# Release Evidence

This directory holds machine-collected proof that a specific commit was verified

It is the only acceptable evidence source for promoting a release gate in `docs/PRODUCTION-READINESS.md`

## Current repository status

This directory contains:

- this evidence-policy document
- `cb1d75d1fb82.json` / `cb1d75d1fb82.md`: machine-generated current-head release evidence with all passing verification suites
- `v0.4-current-head.md`: a historical pre-hardening baseline captured at commit `8f7e2a9` (retained for comparison)

The generated evidence for commit `cb1d75d1fb82` confirms all 446 fast tests, ruff, pyright, inventory validation, docs drift, and wheel build pass with verdict `PASS`.

## What counts as evidence

An evidence record is produced by `scripts/collect_release_evidence.py`, which executes configured commands and records their observed exit status/output metadata

```bash
uv run python scripts/collect_release_evidence.py
uv run python scripts/collect_release_evidence.py --skip-statistical
```

Each complete run writes

- `<sha>.json`: canonical machine-readable evidence object
- `<sha>.md`: human-readable rendering of the same evidence

The canonical record should include

- exact git commit SHA
- collection timestamp and CI identity
- application/runtime dependency versions
- every executed command and exit code
- parsed test results where supported
- wheel/sdist/container identity where part of the release lane
- SHA-256/digest information for release artifacts
- secret-redacted output tails
- overall evidence verdict

## What does not count as evidence

- a hand-written `green`, `PASS`, `production-ready` or `M4` statement
- a test file merely existing in `tests/release/`
- a local result described as a CI result
- results produced for another commit
- a historical baseline
- a planned but unexecuted phase
- pre-marked pass values inside an agent eval fixture
- documentation copied from an older release

## Gate evidence versus component tests

A release test can prove a bounded property without proving the full gate

Examples

- a scope-policy unit test does not prove authenticated HTTP identity reaches the real MCP tool handler
- an ownership-helper test does not prove every MCP resource is protected
- a SQLite job-state test does not prove a statistical worker survives API/container failure
- a logging/metrics unit test does not prove traces, alerts and runbooks exist
- an agent behavior test does not prove all eval fixtures are executed with captured tool traces

The gate definition in `docs/PRODUCTION-READINESS.md` must be satisfied as a whole

## Required production evidence lanes

The target release pack includes evidence from

1. bounded PR/unit/contract/MCP checks
2. real statistical suite
3. remote security E2E suite
4. durable job/restart/storage/backup-recovery suite
5. observability/readiness checks
6. dependency compatibility canary
7. supply-chain/security checks
8. agent quality/negative trace evals
9. clean wheel install smoke
10. container build/start smoke
11. same-commit artifact identity verification

The hardening plan may split these into separate workflows, but the release record must tie the required successful runs back to the same candidate commit

## Secret handling

Evidence must redact

- API keys
- bearer/JWT tokens
- passwords
- credentials/private keys
- authorization headers
- sensitive environment values

The current release-evidence module provides redaction helpers and unit coverage. New evidence sources must pass through the same or stricter redaction contract

## Files

| File | Kind | Meaning |
|---|---|---|
| `v0.4-current-head.md` | historical hand-written baseline | pre-stabilization evidence at `8f7e2a9`; useful for comparison, not current gate proof |
| `<sha>.json` | generated | canonical evidence for exactly `<sha>` |
| `<sha>.md` | generated | rendered summary of the canonical JSON evidence |

Historical files such as `docs/FINAL-REVIEW.md` are provenance only and cannot promote a current gate

## Release decision rule

Before changing any gate status to green

1. identify the exact candidate SHA
2. confirm all required workflows/commands for that gate executed against that SHA
3. confirm evidence artifacts exist and are secret-redacted
4. confirm no required sub-property remains only partially tested
5. update `docs/PRODUCTION-READINESS.md` from that evidence, never in advance of it
