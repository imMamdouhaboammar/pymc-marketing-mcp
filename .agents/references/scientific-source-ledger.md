# Scientific Source Ledger

Checked: 2026-09-17. Local implementation/tests take precedence for server-specific behavior; upstream sources define library semantics only where the MCP actually delegates to them.

| Topic | Local authority | Upstream / primary source |
| --- | --- | --- |
| Capability maturity and public surface | `src/marketing_mcp/capabilities.py`; discovery tests | MCP specification 2026-07-28: https://modelcontextprotocol.io/specification/2026-07-28 |
| MCP Skill delivery | `src/marketing_mcp/mcp/skills.py`; MCP discovery/security tests | Standard MCP tools/resources/resource templates from the 2026-07-28 specification; no non-standard `skills/list` RPC |
| Agent operating protocol (envelopes, jobs, polling, error codes) | `src/marketing_mcp/mcp/envelope.py`; `src/marketing_mcp/errors.py`; `src/marketing_mcp/jobs/service.py`; `src/marketing_mcp/skillpack/evals.py` (three-poll budget) | Repository behavior only |
| Marketing decision framing (break-even, calendar effects, ROAS vocabulary) | `.agents/references/marketing-decision-playbook.md`; allocation/flighting warnings in `src/marketing_mcp/domain/decisions/` | Break-even `1 / margin` is business arithmetic on user-supplied margin; model quantities remain PyMC-Marketing outputs. Hijri-calendar events (Ramadan, Eid) shift about 11 days per Gregorian year and are not captured by Gregorian Fourier seasonality |
| Dataset readiness | `src/marketing_mcp/domain/datasets/validation.py`; dataset service/tests | PyMC-Marketing MMM docs: https://www.pymc-marketing.io/en/latest/getting_started/quickstart/mmm/ |
| MMM/adstock/saturation | typed schemas, adapters, statistical tests | PyMC-Marketing 1.0 docs/source; Jin et al. (2017), *Bayesian Methods for Media Mix Modeling with Carryover and Shape Effects* |
| Sampler and posterior-predictive gate | `src/marketing_mcp/domain/diagnostics/engine.py`; diagnostics tests | PyMC 6 documentation: https://www.pymc.io/ ; ArviZ 1.x documentation: https://python.arviz.org/ |
| Model comparison / PSIS-LOO | model-selection service/domain/tests | ArviZ `compare` / PSIS-LOO: https://python.arviz.org/en/stable/api/generated/arviz.compare.html ; Vehtari, Gelman & Gabry (2017), *Practical Bayesian model evaluation using leave-one-out cross-validation and WAIC* |
| Prior sensitivity | diagnostics service/statistical tests | PyMC/PyMC-Marketing modeling guidance; conclusions remain repository-defined by the MCP operation |
| Lift calibration | calibration service, lineage tests, `CalibrateMMMInput` | PyMC-Marketing calibration docs: https://www.pymc-marketing.io/en/latest/notebooks/mmm/mmm_roas_calibration.html |
| Budget optimization | decision service/domain + statistical tests | PyMC-Marketing `BudgetOptimizer`: https://www.pymc-marketing.io/en/latest/api/generated/pymc_marketing.mmm.budget_optimizer.BudgetOptimizer.html |
| Extrapolation policy | allocation/flighting domain code | Local policy is authoritative; do not present 1.5× historical p95 as a universal methodological threshold |
| BG/NBD purchase model | CLV service/adapter/statistical tests | Fader, Hardie & Lee (2005), *Counting Your Customers the Easy Way: An Alternative to the Pareto/NBD Model*; PyMC-Marketing CLV docs |
| Shifted Beta-Geometric retention | CLV service/adapter/statistical tests | Fader & Hardie retention-model literature; PyMC-Marketing CLV implementation/docs |
| Gamma-Gamma monetary value | CLV service/adapter/statistical tests | PyMC-Marketing CLV implementation/docs and BG/NBD/Gamma-Gamma examples |
| CLV composition | `estimate_customer_lifetime_value` schema/service/tests | PyMC-Marketing CLV docs: https://www.pymc-marketing.io/en/latest/ |
| Job lifecycle/recovery | jobs service/repository/tests | Repository behavior only; do not infer an external durable worker architecture |
| Artifact lifecycle | artifact service/tests | Repository behavior only; server sandbox/export contract is authoritative |

## Installed scientific runtime

The repository lock used during this audit resolves `pymc-marketing==1.0.0`, `pymc==6.0.1`, `arviz==1.3.0`, and `mcp==2.0.0`. Skills must follow this repository’s exposed MCP contract even when upstream documentation describes newer or broader APIs.

## Source integrity rule

When a significant rule is local (decision gates, validation thresholds, job state, extrapolation warning), cite or link the repository implementation/test. When it is a library semantic, prefer upstream source/docs. When it is a methodological claim, prefer the primary paper or current upstream documentation and clearly distinguish examples from defaults.