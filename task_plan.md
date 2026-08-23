# PyMC Marketing MCP — Phase Upgrade Plan

**Goal:** Evolve `pymc-marketing-mcp` from v0.3.0 into a full-spectrum Bayesian marketing intelligence platform covering adstock/saturation model zoo, visual artifact delivery, CLV analytics, and multi-period dynamic planning.

**Baseline:** v0.3.0 — 46/46 tests ✅, 96.79s runtime. Canonical tools: 17 MCP tools, 4 MCP resources, NetCDF + SQLite persistence, MCP 2.0 stdio + HTTP, `pytest-xdist` parallel.

**Next Step:** Begin Phase 1 (Adstock & Saturation Zoo)

---

## Phases

### Phase 1: Adstock & Saturation Zoo + Custom Channel Priors
- **Status:** completed ✅
- **Target Version:** v0.4.0
- **Goal:** Expand from fixed `GeometricAdstock + LogisticSaturation` to the full PyMC-Marketing curve library with per-channel prior control
- **Owner:** adapter layer + schema layer

### Phase 2: Visual Posterior Artifacts (Charts, Curves, Waterfall)
- **Status:** completed ✅
- **Target Version:** v0.4.0
- **Goal:** MCP tools that produce PNG/SVG plots from posterior samples — saturation curves, contribution waterfall, actual vs predicted
- **Owner:** new `services/plotting_service.py` + MCP tool registrations

### Phase 3: Customer Lifetime Value (CLV) Analytics
- **Status:** completed ✅
- **Target Version:** v0.4.0
- **Goal:** BG/NBD + GammaGamma and sBG CLV models exposed as a parallel MCP tool suite for customer analytics
- **Owner:** new `adapters/clv_adapter.py`, `services/clv_service.py`, schema + server tools

### Phase 4: Dynamic Multi-Period Flighting & Profit Optimization
- **Status:** completed ✅
- **Target Version:** v0.4.0
- **Goal:** Optimize weekly media flighting over a full planning horizon with carryover dynamics, target-ROAS constraints, and net-profit objective
- **Owner:** `domain/decisions/flighting.py`, adapter, schema, server

### Phase 5: Bayesian Model Comparison (LOO-CV / WAIC / BMA Stacking)
- **Status:** completed ✅
- **Target Version:** v0.4.0
- **Goal:** PSIS-LOO and WAIC model selection via ArviZ + Bayesian stacking weights across competing MMM specs
- **Owner:** `services/modeling_service.py`, adapter, schema, server

---

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| (none yet) | — | — |

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Phase 1 before CLV | Adstock zoo extends existing MMM code path with lowest integration risk |
| Visual artifacts as Phase 2 | Pure additive delivery, no existing behavioral changes |
| Use `matplotlib`/`arviz.plot_*` | Already transitively installed via ArviZ; no new heavy dep |
| CLV as separate adapter | CLV and MMM share no model state; clean separation via distinct adapter |
