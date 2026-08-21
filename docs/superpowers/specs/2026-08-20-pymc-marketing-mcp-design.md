# PyMC Marketing MCP Design

## Goal
Provide MCP-compatible AI agents with a controlled, reproducible interface to Bayesian MMM calculations performed by PyMC-Marketing.

## Boundaries
The agent interprets business intent and explains structured findings. The server owns dataset validation, model fitting, diagnostics, persistence, posterior summaries, scenario evaluation, budget allocation, uncertainty, provenance, and safety gates. No arbitrary Python, SQL, shell, or filesystem access is exposed.

## Architecture
MCP handlers are thin adapters over application services. Dataset, modeling, diagnostics, and decision services call domain rules and a dedicated PyMC-Marketing adapter. SQLite stores metadata and an artifact store persists model files. Dataset/model IDs are the only public handles.

## Statistical safety
A fitted model cannot be used for budget decisions until diagnostics have run. Rejected models fail closed. Posterior quantities are returned with intervals where available. Missing library capabilities fail explicitly rather than being recreated with ad-hoc formulas.

## Compatibility
V1 targets Python 3.11 to 3.13, PyMC-Marketing 0.19.4.x and MCP Python SDK v2. The MMM adapter supports the migration import path and uses explicit model building plus original-scale contribution variables.

## Testing
Pure domain, schema, storage, security, service, and adapter-contract tests run without PyMC sampling. Real statistical, MCP transport, and Docker integration checks require dependencies that were not available in the assembly runtime.
