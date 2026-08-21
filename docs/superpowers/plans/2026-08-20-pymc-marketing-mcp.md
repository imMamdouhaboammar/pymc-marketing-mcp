# PyMC Marketing MCP Implementation Plan

> **For agentic workers:** Execute each task with test-first changes and verify the complete suite after every behavioral change.

**Goal:** Build a decision-safe MCP server around PyMC-Marketing MMM.

**Architecture:** Thin MCP handlers call application services; domain rules enforce validation and diagnostic gates; the PyMC-Marketing adapter performs statistical work; SQLite and filesystem artifacts provide local persistence.

**Tech Stack:** Python 3.11+, Pydantic, pandas, xarray, ArviZ, PyMC-Marketing 0.19.4.x, MCP Python SDK v2, SQLite, pytest, Docker.

**Spec:** `docs/superpowers/specs/2026-08-20-pymc-marketing-mcp-design.md`

## Completed task groups
- [x] Dataset registration, fingerprinting, inspection, and MMM validation contracts
- [x] Model configuration, status, persistence, and PyMC-Marketing adapter
- [x] Explicit build-model flow with original-scale contribution variables
- [x] Diagnostic engine and hard decision gate
- [x] Contributions, incrementality fail-closed path, response analysis, simulation, and budget allocation interfaces
- [x] MCP tools and resources
- [x] Ingest-root filesystem boundary and security checks
- [x] Synthetic dataset and demo entry point
- [x] stdio and Streamable HTTP entry points
- [x] Docker and local configuration
- [x] Unit/integration tests runnable without statistical dependencies
- [x] Product-first README and architecture/safety/security documentation

## Required environment-backed verification
- [ ] Install declared dependencies with `uv sync --extra dev`
- [ ] Run statistical sampler tests against PyMC-Marketing 0.19.4.x
- [ ] Connect MCP Inspector/client over stdio
- [ ] Connect MCP client over Streamable HTTP `/mcp`
- [ ] Run synthetic end-to-end MMM demo with real sampling
- [ ] Build and start Docker image
