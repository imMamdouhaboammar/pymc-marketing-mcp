# CodeRabbit Coding Environment: PyMC Marketing MCP Server

This document provides the configuration required for **[app.coderabbit.ai/code/environments](https://app.coderabbit.ai/code/environments)** for:

👉 **`imMamdouhaboammar/pymc-marketing-mcp`**

---

## 1. Environment Details

* **Name**: `PyMC Marketing MCP Environment`
* **Assigned Repositories**: `imMamdouhaboammar/pymc-marketing-mcp`

---

## 2. Toolchains

* **Python**: `3.12`
* **Rust**: `1.86` (or `1.85`)

---

## 3. Setup Script (Custom)

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "==> [1/3] Setting up Python 3.12 virtualenv..."
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel

echo "==> [2/3] Installing project dependencies..."
pip install -e '.[dev]' || pip install -r requirements.txt || true

echo "==> [3/3] Checking Rust acceleration crates..."
if [ -d "crates" ]; then
  cargo check --workspace || true
fi

echo "==> Environment ready!"
```

---

## 4. Startup Instructions

```text
This repository is the PyMC Marketing MCP Server (`pymc-marketing-mcp`).

1. Testing:
   Run unit and contract tests with:
   pytest tests/unit tests/contract -v

2. Invariants:
   - Python 3.12 runtime.
   - Enforce server-side diagnostic decision gates (`max_rhat <= 1.05`, zero divergences, `min_bfmi >= 0.2`).
   - Every MCP tool and storage access must be tenant-scoped.
```
