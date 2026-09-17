# Lesson 37: macOS PyO3 Linker Symbol Resolution & Virtual Environment

### Context
Compiling and testing the PyO3 native extension crate `crates/marketing_mcp_fast` on macOS (Darwin arm64/x86_64).

### What happened
Compiling with `cargo build --release` or running `cargo test --no-default-features` on macOS failed with linker errors: `ld: library 'python3.9' not found` or undefined Python C API symbols (`_PyExc_*`).

### Observable symptom
Linker error `clang: error: linker command failed with exit code 1` referencing missing Python framework or missing `PyExc_*` symbols.

### Impact
Developers and automated test runners on macOS could not build or test the native extension locally without CI, breaking local TDD and verification workflows.

### Incorrect assumption
Assumed Cargo and PyO3 would automatically locate the active virtual environment's Python dynamic library or default to dynamic lookup on Darwin.

### Root cause
**Confirmed**. macOS dynamic linker (`ld`) requires explicit flags `-C link-arg=-undefined -C link-arg=dynamic_lookup` for Python C extensions (`cdylib`), and PyO3 defaults to querying the system Python unless `PYO3_PYTHON` is explicitly provided.

### Why the architecture allowed it
The repository lacked a root-level `.cargo/config.toml` defining platform-specific rustflags for Apple Darwin targets.

### Fix
Created `.cargo/config.toml` at repo root and in `crates/marketing_mcp_fast/.cargo/config.toml` configuring:
```toml
[target.aarch64-apple-darwin]
rustflags = ["-C", "link-arg=-undefined", "-C", "link-arg=dynamic_lookup"]

[target.x86_64-apple-darwin]
rustflags = ["-C", "link-arg=-undefined", "-C", "link-arg=dynamic_lookup"]
```
Instructed running tests with `PYO3_PYTHON="$VIRTUAL_ENV/bin/python" cargo test --no-default-features`.

### Verification
34 Rust unit tests pass cleanly locally (`34 passed, 0 failed in 0.00s`), and `cargo clippy` builds with 0 warnings.

### Prevention rule
> **Hybrid Rust/PyO3 repositories must provide version-controlled `.cargo/config.toml` target configurations for Darwin and Linux to ensure portable cross-platform native builds.**

### Reusable lesson
Every native Python extension in a monorepo must specify linker rules for Darwin's dynamic lookup mechanism and bind `PYO3_PYTHON` to the active virtual environment.

### Related code
- `.cargo/config.toml`
- `crates/marketing_mcp_fast/.cargo/config.toml`
- `crates/marketing_mcp_fast/Cargo.toml`

### Related tests
- `cargo test --manifest-path crates/marketing_mcp_fast/Cargo.toml --no-default-features`

### Related lessons
- [14-pyo3-major-version-breaking-api-changes.md](./14-pyo3-major-version-breaking-api-changes.md)
- [27-silent-rust-exclusion-in-production-packaging.md](./27-silent-rust-exclusion-in-production-packaging.md)
- [33-pyo3-build-in-rust-slim-missing-python-interpreter.md](./33-pyo3-build-in-rust-slim-missing-python-interpreter.md)

### Status
Resolved
