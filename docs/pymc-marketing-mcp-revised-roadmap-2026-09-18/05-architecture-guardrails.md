# Architecture Guardrails

## 1. One scientific authority

Python plus PyMC, PyMC-Marketing, ArviZ, xarray, NumPy and approved scientific dependencies remain authoritative for statistical semantics.

Rust may accelerate infrastructure but must not independently define model acceptance, posterior interpretation, calibration semantics, financial utility truth or scientific decision policy.

## 2. Do not bypass the decision gate

Any capability that turns posterior/model output into a commercial recommendation must use the existing decision-access policy or a stricter model-family-specific gate.

Long-term and portfolio models do not inherit MMM approval automatically.

## 3. Extend canonical contracts

Prefer extending:

- `SemanticDatasetContract`
- `ModelingContract`
- model lineage
- artifact manifests
- decision provenance
- repository protocols

Do not create parallel ad-hoc dictionaries or a second readiness framework.

## 4. No silent defaults

For priors, objectives, financial assumptions and model transforms, persist:

- requested
- resolved
- effective

Any automatic recommendation must remain distinguishable from user-supplied configuration.

## 5. No proprietary implementation copying

Simba can be used as evidence of useful problem abstractions.

Do not copy proprietary `simba-mmm` code, docs wording or heuristic constants into this project.

`simba-mcp` is MIT, but even there reuse should happen only when the code materially improves the project and license/attribution requirements are satisfied.

## 6. Prefer official upstream functionality

Before implementing statistical machinery, audit current PyMC-Marketing / PyMC APIs. Use upstream capabilities when they meet the scientific and contract requirements. Wrap rather than fork when possible.

## 7. Evidence-backed maturity

A new tool is not stable because it exists. Keep it experimental until the capability registry points to executable evidence.

## 8. Migration-safe implementation

The current repo and the future Unified Platform target architecture coexist conceptually.

Before coding each feature, determine:

- does the target package already exist in the current worktree?
- is cutover active for this domain?
- does the MCP remain owner, or is it now an adapter?

Never create duplicate ownership merely to match a future architecture document.
