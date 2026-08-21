# Final Review

## Verified in this runtime

- Python source compiles
- Pure unit and contract test suite passes
- PyMC adapter contract calls total and marginal incrementality APIs
- Scenario evaluation uses posterior response sampling rather than optimization
- Budget allocation samples both baseline and recommended response distributions
- Multidimensional validation uses `date + dims` keys and rejects non-rectangular panels
- Multidimensional scenario allocations and cell constraints are converted to `channel x dims` xarray contracts
- Diagnostic gate combines sampler and posterior predictive evidence
- Decision calls are blocked without diagnostic approval
- Dataset registration is restricted to the configured ingest root at the MCP boundary
- Original-scale contribution variables are added before model fitting
- No MCP tool exposes arbitrary Python, SQL, shell, or caller-selected artifact paths
- SQLite metadata persists through the storage interface

## Not executable in this runtime

The runtime does not contain `pymc-marketing` or the `mcp` package and does not allow outbound package installation. Therefore these claims are intentionally not marked verified here:

- real Bayesian sampling with the pinned PyMC-Marketing dependency
- real incrementality calculation on a fitted MMM artifact
- real budget optimization and posterior scenario sampling with PyMC-Marketing
- real MCP Inspector/client invocation
- Streamable HTTP handshake
- Docker dependency build
- complete statistical demo

Run the commands in the README in a dependency-enabled Python 3.11 to 3.13 environment to close these checks.
