# pymc-marketing-mcp

Decision-safe MCP server exposing PyMC-Marketing (Bayesian MMM) as tools.
Python 3.12+, hatchling build, `src/marketing_mcp/` layout, pytest + ruff.

## Commands

```bash
uv run pytest -m "not statistical"   # fast tests (excludes the sampling suite)
uv run pytest -m statistical          # sampling tests (slow; real PyMC-Marketing fits)
uv run pytest                         # everything, including the statistical suite
uv run ruff check src tests scripts   # lint
uv run python scripts/generate_capability_inventory.py --check  # capability inventory drift
uv run python scripts/check_docs_drift.py                       # documentation drift
```

There is no default fast filter: bare `uv run pytest` runs the statistical suite too, so use
`-m "not statistical"` for a fast loop.

## Skills

Invoke these installed skills (`~/.agents/skills/`) when working on matching tasks:

| Task | Skill |
|---|---|
| Writing/fixing tests under `tests/` | `python-testing-patterns`, `pytest-coverage` |
| Refactoring services/models in `src/marketing_mcp/` | `python-design-patterns` |
| Adding/changing MCP tools or validation | `mcp-server-patterns` |
| Editing `Dockerfile` / `docker-compose.yml` | `docker-patterns` |
| Optimizing pandas/numpy/xarray hot paths | `python-performance-optimization` |

## Conventions

- Statistical tests are marked `statistical`; keep fast loops on `-m "not statistical"`.
- Tool contracts live in `docs/TOOL-CONTRACTS.md` — update alongside tool changes, and regenerate
  `docs/CAPABILITIES.md` with `scripts/generate_capability_inventory.py` when tools change.
- Documentation claims about versions, tools, transforms, transports, and the decision gate are
  checked by `scripts/check_docs_drift.py`; keep them true.
- Line length 100 (ruff), target py311+ syntax.
