# Failure Lesson 27 — Silent Rust Exclusion in Production Containers & Dynamic Linker Bypass

**Date Encountered**: 2026-09-16  
**Component**: `Dockerfile`, `marketing_mcp/accelerators/__init__.py`, `crates/marketing_mcp_fast`  
**Severity**: High (Production deployment silently ran in pure Python fallback without native acceleration)  
**Impact Area**: Production Container Packaging / CI Verification / Runtime Engine Health  

---

## 1. Executive Summary

An architectural audit of production artifacts revealed that while the Rust accelerator crate `marketing_mcp_fast` compiled locally during development, **it was completely absent from the shipped production Docker image and release wheels**:
1. **Dockerfile Omission**: The existing `Dockerfile` was a single-stage Python build that never copied `crates/`, never installed the Rust toolchain, and never built the extension `.so`.
2. **Silent Fallback Masking**: Because the accelerator bridge was designed with a "zero-downtime Python fallback", the runtime silently fell back to pure Python in production without throwing errors or warnings.
3. **macOS Loader Defect**: Even in local environments where `cargo build --release` produced `libmarketing_mcp_fast.dylib`, Python 3.12's `importlib.util.spec_from_file_location` returned `spec.loader = None` because standard Python only associates `ExtensionFileLoader` with filenames ending in `.so`. Consequently, `is_rust_accelerated()` silently returned `False` even when the compiled dylib was on disk!

---

## 2. Root Cause Analysis

### A. Missing Container Multi-Stage Pipeline
The build pipeline treated `pymc-marketing-mcp` as a pure Python package managed by Hatchling, omitting the native compilation step from CI and Docker packaging.

### B. Fallback Camouflage
Because unit tests asserted `info["rust_accelerated"] == is_rust_accelerated()`, when `is_rust_accelerated()` returned `False`, `False == False` passed without alerting developers that native acceleration was dead.

### C. Extension Loader Protocol on Darwin
On macOS Mach-O, shared libraries have extension `.dylib` while Python C-extensions expect `.so`. Calling `spec_from_file_location` without explicitly passing `loader=ExtensionFileLoader("marketing_mcp_fast", str(found))` failed to assign an execution loader.

---

## 3. Resolution & Hardening

1. **Multi-Stage Production Dockerfile**:
   - Stage 1 (`rust-builder`): Builds `crates/marketing_mcp_fast` using `cargo build --release`.
   - Stage 2 (`runtime`): Copies `libmarketing_mcp_fast.so` directly into `/app/src/marketing_mcp/accelerators/marketing_mcp_fast.so`.
   - **Fail-Closed Container Assertion**: Added `RUN python -c "from marketing_mcp.accelerators import is_rust_accelerated; assert is_rust_accelerated()"` to guarantee that a container failing to activate native acceleration fails the build.
2. **Hardened Dynamic Library Loader**:
   - In `src/marketing_mcp/accelerators/__init__.py`, imported `_frozen_importlib_external.ExtensionFileLoader` and passed it explicitly to `spec_from_file_location`.
   - Added package-local search (`pkg_dir / "marketing_mcp_fast.so"`) so installed wheel and container artifacts take precedence.
3. **Telemetry & Health Endpoint Exposure**:
   - Updated `/health` and `/ready` probes to expose `"interaction_engine": {"backend": "rust-native", "version": "0.1.0", "rust_accelerated": true}`.

---

## 4. Architectural Invariants Established

1. **Fail-Closed Container Activation**: Production container builds must assert native acceleration activation at build time. No release artifact may claim native performance without automated proof.
2. **Explicit Health Exposure**: Operational endpoints (`/health`, `/ready`) must expose the active accelerator backend and version to monitoring systems.
