# Lesson 44: Exact-Candidate SHA Binding & Single-Build Promotion

### Context
Release pipeline integrity, supply-chain verification, and artifact promotion in `.github/workflows/release.yml` (Issue #12).

### What happened
Conventional release pipelines checkout a release tag, run tests, and subsequently execute an unconstrained `build` step before publishing. If the checkout was mutable or if local build scripts re-ran without strict hash checks, artifacts published to PyPI or container registries could diverge from the exact commit tested in CI, introducing unreviewed changes or corrupted build caches into production.

### Observable symptom
Absence of machine-verifiable proof that published wheel, sdist, and container images correspond byte-for-byte to the exact commit SHA approved during quality gates.

### Impact
Critical supply-chain security vulnerability: risk of publishing untested code, dependency drift during publication, or silent divergence between source git tags and distributed binary artifacts.

### Incorrect assumption
Assumed that checking out a tag and running `build` after `test` guarantees that published artifacts match the tested code.

### Root cause
**Confirmed**. Two-phase build pipelines that rebuild artifacts after testing break the chain of custody. A release pipeline must build artifacts once, test those exact artifact bytes, and publish only the verified hashes.

### Why the architecture allowed it
The release workflow relied on sequential step execution rather than cryptographic candidate binding and digest promotion.

### Fix
1. Enforced strict SHA equality between requested release tag and checkout HEAD:
   ```bash
   TAG_SHA=$(git rev-parse "${TARGET_TAG}^{commit}")
   CANDIDATE_SHA=$(git rev-parse HEAD)
   test "${TAG_SHA}" = "${CANDIDATE_SHA}"
   ```
2. Implemented Single-Build Promotion: Python packages (`wheel`, `sdist`) and containers are built exactly once, hashed (`sha256sum`), and smoke-tested against their exact file digests.
3. The publication step verifies digests before promoting artifacts to destination registries without any rebuild.

### Verification
`tests/release/test_candidate_provenance.py` passes all 3 tests:
- `test_release_checkout_is_bound_to_the_requested_candidate`
- `test_release_builds_once_and_smokes_every_exact_artifact`
- `test_publication_is_explicit_and_cannot_rebuild_or_publish_historical_evidence`

### Prevention rule
> **Every release artifact (wheel, sdist, container) must be built exactly once from an immutable candidate commit SHA, verified in place via cryptographic checksums, and published without rebuilding.**

### Reusable lesson
Applies to all multi-stage CI/CD pipelines (Docker images, NPM packages, Python wheels, Helm charts): separate build/verification from promotion; promotion should only copy verified digests, never rebuild source code.

### Related code
- `.github/workflows/release.yml`
- `src/marketing_mcp/release_evidence.py`

### Related tests
- `tests/release/test_candidate_provenance.py`
- `tests/unit/test_release_evidence.py`

### Related lessons
- [27-silent-rust-exclusion-in-production-packaging.md](./27-silent-rust-exclusion-in-production-packaging.md)
- [34-dockerfile-posix-sh-process-substitution-syntax-error.md](./34-dockerfile-posix-sh-process-substitution-syntax-error.md)

### Status
Resolved
