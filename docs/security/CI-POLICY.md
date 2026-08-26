# Security CI and Supply-Chain Policy

This document defines the automated security checks and failure policies enforced in CI.

## 1. Zero Committed Secrets Policy

CI fails immediately if any of the following patterns are committed outside of explicit mock unit test fixtures:
- Raw API keys (`sk-live-*`, `mcp_live_*`)
- Unhashed secret tokens (`keyHash: fullSecret`)
- Plaintext JWT signing secrets or private keys
- Basic authentication credentials in URLs or environment files

## 2. Dependency Vulnerability Audits

- Direct dependencies must not contain known Critical or High severity CVEs without an approved and documented mitigation.
- Security scans run in CI on every PR and nightly.

## 3. Container & Supply-Chain Hardening

- Container base images must use non-root execution (`USER appuser`).
- No build secrets or dashboard `.env.local` files may be copied into container layers.
- A machine-readable SBOM (SPDX/CycloneDX) is generated for each production release build.
