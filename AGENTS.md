# pymc-marketing-mcp

Decision-safe MCP server exposing PyMC-Marketing (Bayesian MMM) as tools.
Python 3.12+, hatchling build, `src/marketing_mcp/` layout, pytest + ruff.

## Commands

```bash
uv run pytest                      # fast tests (skips statistical marker)
uv run pytest -m statistical       # sampling tests (slow)
uv run pytest -m mcp               # MCP SDK integration tests
uv run ruff check src tests        # lint
```

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

- Statistical tests are marked `statistical`; keep default runs fast and deterministic.
- Tool contracts live in `docs/TOOL-CONTRACTS.md` — update alongside tool changes.
- Line length 100 (ruff), target py311+ syntax.
