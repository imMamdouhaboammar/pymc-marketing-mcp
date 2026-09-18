# PyMC Marketing MCP - Revised Core Capability Roadmap

Audit baseline: repository `imMamdouhaboammar/pymc-marketing-mcp`, branch `main`, commit `1182e64a659ed341abad2a7c17ce88f0d9489a56`, reviewed 2026-09-18.

This revision replaces the earlier plan that treated several capabilities as greenfield. The current repository already contains a much stronger data-intelligence, decision, prior-sensitivity, financial, panel-MMM, artifact, and platform-migration foundation than the previous plan assumed.

The roadmap now follows four rules:

1. Do not rebuild capabilities that already exist.
2. Extend the existing canonical owner instead of creating parallel services.
3. Preserve the current decision gate, provenance, lineage, capability registry, and statistical evidence model.
4. Treat the Unified Platform migration ledger as target ownership guidance, without assuming target monorepo directories already exist in this repository.

Read in this order:

- `01-current-state-and-corrections.md`
- `02-revised-gap-matrix.md`
- `03-revised-roadmap.md`
- `04-implementation-tasks.md`
- `05-architecture-guardrails.md`
- `06-coding-agent-brief.md`
