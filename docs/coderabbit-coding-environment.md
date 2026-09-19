# CodeRabbit Coding Environment: PyMC Marketing MCP Server

This document provides the configuration required for **[app.coderabbit.ai/code/environments](https://app.coderabbit.ai/code/environments)** for:

👉 **`imMamdouhaboammar/pymc-marketing-mcp`**

---

## 1. Environment Details

* **Name**: `PyMC Marketing MCP Environment`
* **Assigned Repositories**: `imMamdouhaboammar/pymc-marketing-mcp`

---

## 2. Toolchains

* **Python**: `3.12` baseline; project support range is `>=3.12,<3.14`
* **Rust**: stable toolchain, matching the repository Docker build

---

## 3. Setup Script (Custom)

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> [1/3] Setting up Python 3.12 environment..."
python3.12 --version
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel uv

echo "==> [2/3] Installing locked project dependencies..."
uv sync --frozen --extra dev

echo "==> [3/3] Verifying Rust acceleration crates..."
cargo --version
cargo check --workspace

echo "==> Environment ready: dependency installation and Rust checks passed."
```

---

## 4. Startup Instructions

```text
This repository is the PyMC Marketing MCP Server (`pymc-marketing-mcp`).

1. Testing:
   Run unit and contract tests with:
   pytest tests/unit tests/contract -v

2. Invariants:
   - Preserve compatibility with the declared Python range `>=3.12,<3.14`, with Python 3.12 as the CI baseline.
   - Use `src/marketing_mcp/domain/diagnostics/engine.py` and `docs/DECISION-INTEGRITY.md` as the production decision-gate source of truth: reject on any divergences (`> 0`), `max_rhat > 1.05`, minimum bulk ESS `< 50`, or 94% posterior-predictive coverage `< 0.50` when available; preserve documented caution bands without upgrading them to hard failures.
   - Preserve tenant/ownership boundaries for tenant-aware MCP and persistence paths; verify intentional local/stdio behavior before flagging it.
```
