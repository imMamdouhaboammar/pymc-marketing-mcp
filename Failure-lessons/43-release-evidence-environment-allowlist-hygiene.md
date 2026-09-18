# Lesson 43: Release Evidence Environment Allowlist Hygiene

### Context
Collection of machine-verifiable release evidence and audit provenance in `src/marketing_mcp/release_evidence.py` (Issue #5).

### What happened
Release evidence collection originally captured a full snapshot of `os.environ` and applied a regex/denylist to scrub known sensitive variable names (such as `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`, etc.). Any unrecognized, custom, or newly introduced environment variable containing secrets or internal paths would be serialized directly into release JSON manifests and markdown summaries.

### Observable symptom
An audit identified that internal process paths, local tool tokens, or developer-specific environment variables could leak into publicly published release evidence if their names did not match the static denylist patterns.

### Impact
High security and privacy risk of secret leakage and credential exposure in public release artifacts and CI logs.

### Incorrect assumption
Assumed that an environment variable denylist is sufficient to protect against secret leakage in audit logs.

### Root cause
**Confirmed**. Denylists are fundamentally unsafe for security boundaries because they rely on enumerating all possible bad keys in an open-ended universe.

### Why the architecture allowed it
The evidence collector treated ambient OS environment capture as an all-inclusive dump rather than an explicit minimal provenance record.

### Fix
Replaced the full environment capture and denylist with an immutable, strict allowlist:
```python
_SAFE_ENV_KEYS = frozenset(
    {
        "CI",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "PYTHONHASHSEED",
        "RUNNER_ARCH",
        "RUNNER_OS",
    }
)
```
Only variables explicitly enumerated in `_SAFE_ENV_KEYS` are captured. All other environment variables are discarded completely.

### Verification
`tests/unit/test_release_evidence.py::test_unknown_environment_keys_are_not_persisted` asserts that sentinel variables not in `_SAFE_ENV_KEYS` are never recorded in JSON or markdown outputs.

### Prevention rule
> **Audit, logging, and provenance systems must always enforce an explicit allowlist of safe fields. Ambient environment dumps with denylist filtering are strictly prohibited.**

### Reusable lesson
Applies to error reporters, telemetry payloads, release manifests, and container metadata: never capture the ambient environment by default; specify the exact schema of allowable provenance fields.

### Related code
- `src/marketing_mcp/release_evidence.py`
- `scripts/collect_release_evidence.py`

### Related tests
- `tests/unit/test_release_evidence.py::test_unknown_environment_keys_are_not_persisted`

### Related lessons
- [16-artifact-export-credential-leakage.md](./16-artifact-export-credential-leakage.md)
- [23-default-tenant-metadata-leakage.md](./23-default-tenant-metadata-leakage.md)

### Status
Resolved
