# Revised Gap Matrix

| Concept | Current state at 1182e64 | Revised action | Priority |
| --- | --- | --- | --- |
| Data quality / identifiability | Strong implementation exists in `intelligence/*` | Extend, do not rebuild. Add missing diagnostics only where evidence shows a gap, and feed severity into suitability / decision policy | P0 integration work, not new engine |
| Risk-aware optimization | Posterior distributions and robust optimizer exist, but no explicit risk utility such as downside/CVaR/expected-regret objective found | Add a typed posterior utility objective layer on top of existing budget optimizer and flighting paths | P0 |
| Financial decision layer | Net-profit flighting and CLV discounting already exist | Unify financial semantics and make them reusable across simulation, allocation, flighting, CLV and future portfolio decisions | P0 |
| Prior recommendation | Channel priors + sensitivity exist | Add evidence-aware prior recommendation, provenance, confidence and validation workflow | P1 |
| Experiment evidence | Lift calibration exists | Add persistent Experiment Evidence Registry and link it to calibration, lineage and next-measurement recommendations | P1 |
| Carryover accounting | Carryover-aware optimization exists | Add auditable source-period response ledger, not another carryover optimizer | P1 |
| Long-term effects | No first-class long-term brand/VAR/IRF engine found | Add pluggable long-term-effects model family with independent scientific design | P2 |
| Portfolio / halo / cannibalization | Panel MMM and dimensional allocation exist, but no explicit portfolio effect semantics found | Extend dimensions into a typed portfolio graph/effect layer, with learned or evidence-backed cross-entity effects | P2 |
| Canonical channel mapping | Semantic channel inference exists | Extend semantic contract with stable canonical channel identity and spend/activity mapping where needed, rather than adding a separate mapping subsystem | P1 |
| Resolved / effective config | Canonical ModelSpec and provenance foundations exist | Add explicit requested vs resolved vs effective model/decision config snapshots to prevent silent interpretation drift | P1 |
| Attribution convention | Contributions and iROAS exist | Add explicit attribution convention metadata and reconciliation assumptions to result contracts | P1 |
| Unified Platform target ownership | Migration ledger exists; target directories absent here | Every new capability must declare current owner + future target owner + cutover gate | P0 architecture rule |
