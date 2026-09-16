# Failure Lesson 33: PyO3 Build in Slim Rust Container Missing Python 3.x Interpreter & ABI Mismatch

## Executive Summary & Context
During production container builds on Google Cloud Build (`scripts/fast_deploy.sh`), compilation of the native Rust extension `crates/marketing_mcp_fast` in Stage 1 failed during `cargo build --release` with:
```text
error: failed to run custom build command for `pyo3-build-config v0.23.5`
...
error: no Python 3.x interpreter found
warning: build failed, waiting for other jobs to finish...
The command '/bin/sh -c cargo build --release' returned a non-zero code: 101
```

## Symptom & Error Signature
- **Pipeline**: Google Cloud Build (`gcloud builds submit --tag ... .`)
- **Failing Step**: Step 5/21: `RUN cargo build --release`
- **Error Trace**:
  ```text
  --- stdout
  cargo:rerun-if-env-changed=PYO3_CONFIG_FILE
  cargo:rerun-if-env-changed=PYO3_NO_PYTHON
  cargo:rerun-if-env-changed=PYO3_ENVIRONMENT_SIGNATURE
  cargo:rerun-if-env-changed=PYO3_PYTHON
  ...
  --- stderr
  error: no Python 3.x interpreter found
  ```

## Root Cause Analysis
1. **Missing Python in Builder Image**: The base image `rust:1-slim` is a stripped Debian image that contains Rust and Cargo but deliberately omits Python runtime interpreters and header packages (`python3`, `python3-dev`).
2. **PyO3 Build-Time Detection Requirement**: In PyO3 0.23, when compiling with the `extension-module` feature without explicit static configuration, `pyo3-build-config` executes a build-script that inspects the local environment for an active Python 3.x executable (`python3`, `python`, or `PYO3_PYTHON`) to query target sysconfig parameters, header paths, and libpython linkage requirements.
3. **ABI Incompatibility Danger**: If one installs Debian Bookworm's default `python3` package into `rust:1-slim`, it installs Python 3.11.2. However, Stage 2 of the multi-stage Docker build is `python:3.12-slim` (Python 3.12.13). Compiling a C-extension against Python 3.11 headers and then loading it into Python 3.12 without `abi3` creates an unimportable shared object due to CPython ABI changes between minor versions.

## Resolution & Architecture Diff
Base the `rust-builder` multi-stage container on `python:3.12-slim` directly and install the stable Rust toolchain via `rustup`. This provides two major guarantees:
1. `pyo3-build-config` immediately locates `/usr/local/bin/python3` (Python 3.12) and its official headers.
2. The compiled `.so` binary is 100% ABI-identical with the Stage 2 `python:3.12-slim` runtime.

```dockerfile
# Before:
FROM rust:1-slim AS rust-builder
WORKDIR /build
COPY crates ./crates
WORKDIR /build/crates/marketing_mcp_fast
RUN cargo build --release

# After:
FROM python:3.12-slim AS rust-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/root/.cargo/bin:${PATH}"
COPY crates ./crates
WORKDIR /build/crates/marketing_mcp_fast
RUN cargo build --release
```

Additionally, expanded `dylib_candidates` in `src/marketing_mcp/accelerators/__init__.py` to check `pkg_dir / "libmarketing_mcp_fast.so"` alongside `marketing_mcp_fast.so`.

## Invariants Derived
1. **Identical Builder-Runtime Minor Python Version**: Native PyO3 extensions built without ABI3 must be compiled in an environment whose CPython minor version precisely matches the deployment container runtime.
2. **Preflight Python Availability for PyO3**: Multi-stage Rust build environments targeting CPython extensions must provide `python3` in `$PATH` before executing `cargo build`.
