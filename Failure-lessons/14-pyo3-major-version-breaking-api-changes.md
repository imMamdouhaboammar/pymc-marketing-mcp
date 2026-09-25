# Failure Lesson 14 — PyO3 Major Version Breaking API Changes (0.23 → 0.29)

**Date Encountered**: 2026-09-16  
**Session**: Revision 2 test report remediation & Cloud Run deployment  
**Severity**: High (Blocks Rust extension compilation — must not merge without migration pass)  
**Impact Area**: Dependency Management / Rust Extension / CI

---

## Executive Summary

Dependabot opened a security-motivated PR bumping `pyo3` from `0.23` to `0.29` in `crates/marketing_mcp_fast`. While pyo3 0.29 contains genuine security fixes (missing `Sync` bound on `PyCFunction::new_closure`, out-of-bounds read in `BoundTupleIterator`), the 6-minor-version jump introduces breaking API changes that prevent our Rust C-extension from compiling.

The PR was deferred with a comment explaining this and is **not safe to merge without a migration pass** first.

---

## Symptom & Error Signature

Running `cargo check` against the dependabot Cargo.toml (`pyo3 = "0.29"`) produced 7 compile errors:

```
error[E0034]: multiple applicable items in scope
  --> src/diagnostics.rs:101
   |
   | ) -> PyResult<PyObject> {
   |      ^^^^^^^^ multiple `wrap` found
   = note: candidate #1 is defined in an impl for the type `pyo3::impl_::wrap::IntoPyObjectConverter<Result<T, E>>`
   = note: candidate #2 is defined in an impl for the type `pyo3::impl_::wrap::IntoPyObjectConverter<T>`

error: could not compile `marketing_mcp_fast` (lib) due to 7 previous errors
```

---

## Root Cause Analysis

PyO3 0.24+ introduced the `IntoPyObject` trait as a replacement for `ToPyObject` and `IntoPy<PyObject>`. The 0.24–0.29 migration guide lists:

- `PyObject` is deprecated in favor of `Bound<'py, PyAny>`
- `IntoPy<PyObject>` → `IntoPyObject`
- Return type ambiguity in `#[pyfunction]` blocks returning `PyResult<PyObject>` now triggers multi-candidate resolution errors
- GIL-ref constructors changed

Because we jumped 6 minor versions in a single dependabot bump, all APIs must be updated simultaneously.

---

## Resolution Plan

**Do NOT merge PR #18 until the following steps are completed:**

1. Read the pyo3 migration guides for versions 0.24 through 0.29:
   `https://pyo3.rs/v0.29.0/migration.html`

2. Update all `#[pyfunction]` signatures in:
   - `src/lib.rs`, `src/csv_preflight.rs`, `src/diagnostics.rs`, `src/quantiles.rs`, `src/sparklines.rs`
   
   To use `Bound<'py, PyAny>` return types and `IntoPyObject` trait bounds.

3. Replace `PyObject` usages with `Bound<'py, PyAny>` / `Py<T>` idioms.

4. Verify `cargo test --no-default-features` passes all 14 Rust unit tests.

5. Verify Python fallback parity tests still pass (`pytest tests/unit/`).

---

## Immediate Action Taken

- Reverted local `Cargo.toml` back to `pyo3 = "0.23"` (the working version).
- Restored `Cargo.lock` to pre-check state.
- Added blocking comment to PR #18 explaining the incompatibility and migration requirement.
- Working tree confirmed clean: `git status` shows nothing to commit.

---

## Invariants & Prevention Rules

1. **Never auto-merge Rust dependency bumps that cross a major PyO3 version boundary** without running `cargo check --workspace` locally first.

2. **Pin to `pyo3 = "0.23"` until explicit migration is planned**; document in `Cargo.toml` with a comment referencing this lesson.

3. **Security-motivated PRs from dependabot still require compile verification** before merge. The security value of the upgrade is real, but breaking compilation defeats it.

4. **Keep a migration tracking issue or PR linked from the comment** so the upgrade doesn't get lost.

---

## Verification Evidence

```bash
# Confirmed Cargo.toml is restored to working state
$ grep pyo3 crates/marketing_mcp_fast/Cargo.toml
pyo3 = { version = "0.23" }

# Confirmed 14 Rust workspace tests still pass
$ cargo test --workspace
test result: ok. 14 passed; 0 failed

# Confirmed 594 Python tests pass (no regression)
$ pytest tests/ -v
594 passed in 334.49s
```

---

## Resolution (2026-09-25)

The migration pass landed and `pyo3` is on `0.29`, which closes RUSTSEC-2025-0020, RUSTSEC-2026-0177 and GHSA-36hh-v3qg-5jq4.

The crate needed two mechanical changes in `src/lib.rs`:

- `PyResult<PyObject>` became `PyResult<Py<PyAny>>` (`PyObject` was removed); `Ok(dict.into())` still converts
- `Bound::downcast::<T>()` became `Bound::cast::<T>()`

The `E0034` "multiple `wrap` found" errors listed above were a side effect of the missing `PyObject` type and went away with the first change.

Verified with `cargo fmt --check`, `cargo clippy --all-targets --all-features -D warnings`, `cargo test --no-default-features` (34 passed), the release build loading as `rust-native`, and the Python suite with the native extension active.
