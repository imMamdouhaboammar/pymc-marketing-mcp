# Release evidence

This directory holds **machine-collected** proof that a specific commit was verified. It is the
only acceptable input to a gate decision in `docs/PRODUCTION-READINESS.md`.

## What counts as evidence

An evidence record is produced by `scripts/collect_release_evidence.py`, which executes each
command and records the exit code the process actually returned:

```bash
uv run python scripts/collect_release_evidence.py                    # full verification set
uv run python scripts/collect_release_evidence.py --skip-statistical # fast subset
```

Each run writes two files named after the commit SHA:

- `<sha>.json` — the canonical evidence object (deterministic, sorted keys, secrets redacted)
- `<sha>.md` — a rendered summary of the same object

The JSON object is defined by `marketing_mcp.release_evidence.collect_release_evidence` and
contains the commit SHA, collection timestamp, platform, Python version, runtime dependency
versions, application version, CI provenance, every executed command with its exit code and parsed
test counts, build artifact sizes and SHA-256 hashes, and an overall `PASS`/`FAIL` verdict.

## What does not count as evidence

- A hand-written pass/fail claim in any Markdown file. Test counts are parsed from real pytest
  output; the collector raises `ValueError` if a command record has no observed exit code.
- Results from a different commit. The verdict applies only to `commit_sha`.
- Results from a phase that was planned but not executed.
- Locally passing results presented as CI results. The `ci` block records whether the run happened
  in CI and, if so, which provider and run ID.

## Secret handling

Command strings, output tails, and environment values are passed through
`marketing_mcp.release_evidence.redact_secrets`. Environment variables whose names match
`API_KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `CREDENTIAL`, or `PRIVATE_KEY` are replaced entirely, and
credential-shaped fragments (`--api-key …`, `?token=…`, `Authorization: Bearer …`) are masked
inside recorded text. `tests/unit/test_release_evidence.py` asserts this.

## Files in this directory

| File | Kind | Meaning |
|---|---|---|
| `v0.4-current-head.md` | hand-written baseline record | The pre-stabilization baseline: what was executed at commit `8f7e2a9`, plus the defect ledger. Superseded for gate purposes by generated `<sha>.json` records. |
| `<sha>.json` / `<sha>.md` | generated | Machine-collected evidence for that commit. |

Historical review documents that predate this discipline (for example `docs/FINAL-REVIEW.md`)
describe past work and are **not** current release evidence.
