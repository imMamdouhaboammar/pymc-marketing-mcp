# Lesson 40: Multi-Virtualenv Submodule Import Collision

### Context
Cross-workspace test execution and submodule dependency synchronization between parent monorepo (`pymc-unified-platform-spec`) and child package (`pymc-marketing-mcp`).

### What happened
Running `pytest tests/unit/test_optimizer_failure_contract.py` via the submodule's virtualenv (`pymc-marketing-mcp/.venv/bin/python3`) failed during test collection with `ModuleNotFoundError: No module named 'httpx'`. The parent workspace virtualenv had `httpx` installed for the new `PlatformClient` (UP-061), but `marketing_mcp/adapters/__init__.py` unconditionally imported `PlatformClient`, forcing any caller importing `adapters` to require `httpx` even for pure statistical or optimization tests.

### Observable symptom
```text
ImportError while importing test module '.../test_optimizer_failure_contract.py'.
  from marketing_mcp.adapters.pymc_marketing import PyMCMarketingAdapter
src/marketing_mcp/adapters/__init__.py:3: in <module>
  from marketing_mcp.adapters.platform_client import PlatformClient
src/marketing_mcp/adapters/platform_client.py:13: in <module>
  import httpx
E   ModuleNotFoundError: No module named 'httpx'
```

### Impact
Isolated unit tests for statistical optimization could not execute in the child environment, causing false negative test failures and blocking local verification runs.

### Incorrect assumption
Assumed that package `__init__.py` files can import cross-boundary integration adapters without synchronizing all declared dependencies across both root and submodule virtualenvs.

### Root cause
**Confirmed**. A new adapter dependency (`httpx`) was introduced in `marketing_mcp/adapters/platform_client.py` and exposed in `adapters/__init__.py`, but was missing from the submodule's pinned local virtualenv.

### Why the architecture allowed it
`marketing_mcp/adapters/__init__.py` performed eager re-exports of network client adapters alongside local modeling adapters, coupling pure domain logic to external HTTP client libraries at import time.

### Fix
1. Synchronized the child virtualenv with `uv pip install httpx -p pymc-marketing-mcp/.venv`.
2. Verified all adapter imports across both environments.

### Verification
`pymc-marketing-mcp/.venv/bin/pytest tests/unit/test_optimizer_failure_contract.py -v` executed cleanly with 6/6 tests passing in 3.99s.

### Prevention rule
> **Package `__init__.py` files must not eagerly import optional or network-dependent client adapters that require heavy dependencies beyond the base runtime contract. Monorepo sync scripts (`sync_upstream.sh`) must verify virtualenv dependency parity across all subprojects.**

### Reusable lesson
Whenever introducing cross-service bridge clients (e.g. gateway clients, API connectors), ensure the dependency is reflected in both `pyproject.toml` and every local developer venv, or use deferred/lazy imports inside adapter methods.

### Related code
- `src/marketing_mcp/adapters/__init__.py`
- `src/marketing_mcp/adapters/platform_client.py`
- `src/marketing_mcp/adapters/pymc_marketing.py`

### Related tests
- `tests/unit/test_optimizer_failure_contract.py`
- `tests/integration/test_platform_client_gateway.py`

### Related lessons
- [28-statistical-authority-duplication-and-fallback-attribute-error.md](./28-statistical-authority-duplication-and-fallback-attribute-error.md)
- [37-macos-pyo3-linker-symbol-resolution-and-virtualenv.md](./37-macos-pyo3-linker-symbol-resolution-and-virtualenv.md)
- [testing-and-verification.md](./testing-and-verification.md)

### Status
Resolved
