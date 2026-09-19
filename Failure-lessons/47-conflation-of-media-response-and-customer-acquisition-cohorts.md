# Lesson 47: Conflation of Media Response Cohorts and Customer Acquisition Cohorts

### Context
Response cohort accounting in marketing domain contracts (`src/marketing_mcp/domain/cohorts/contracts.py`, `ledger.py`).

### What happened
The platform included a domain module called `ResponseCohortLedger` (T7). Its module docstring claimed:
```text
Tracks commercial outcome realizations by acquisition cohort, maturity curves,
and observational lag. Reconciles cohort contributions with aggregate MMM target series.
```
However, the underlying data structure was `CohortRecord(acquired_customers=..., period_revenues=...)`, built from customer transaction logs via `extract_cohorts_from_transactions(customer_id_col, date_col, value_col)`.

This created a severe domain conflation: customer lifetime transaction cohorts (CLV) were given the name of media response cohorts and claimed to reconcile directly with macro-economic MMM aggregate response series.

### Observable symptom
Scientific integrity audit (Candidate Gap 4) highlighted the conflict:
```text
Do not confuse:
customer acquisition revenue cohorts
with:
media source-period response cohorts

Desired media accounting is approximately:
spend at t -> response at t -> carryover response t+1 -> carryover response t+2 -> ... -> financial valuation
Reuse fitted posterior and adstock mechanics. Never implement a second adstock system.
Require reconciliation to authoritative aggregate response.
```

### Impact
Callers or AI agents asking for "media response cohorts" or attempting to reconcile MMM channel spend carryover would be routed to a customer transaction table requiring `customer_id` microdata, which either failed or caused nonsensical comparisons between customer repeat-purchase revenue and macro marketing response.

### Incorrect assumption
Assumed a single generic "cohort" ledger abstraction could represent both customer retention over calendar time and marketing spend carryover decay over adstock lag horizons.

### Root cause
**Confirmed**. Conflation of two completely different causal mechanisms, physical entities, and temporal horizons:
1. **Customer Acquisition Cohorts**: Entity is a customer population acquired in period $t$; metric is customer retention / repeat revenue across subsequent periods.
2. **Media Response Cohorts**: Entity is marketing spend $S_{c,t}$ deployed in source period $t$ on channel $c$; metric is immediate incremental response ($t+0$) plus adstock carryover responses ($t+1..t+L$) across lag periods.

### Why the architecture allowed it
The original task ticket specified "Response Cohort Ledger" without pinning the formal mathematical entity (customer vs spend dollar). The engineer implemented customer transaction cohorts because transaction datasets were readily available, but labeled the file with marketing response reconciliation wording.

### Fix
1. **RFC 003**: Published `docs/rfcs/003-media-response-cohort-accounting.md` formalizing the two distinct cohort domains.
2. **Contracts**: Separated `src/marketing_mcp/domain/cohorts/contracts.py`:
   - `CustomerAcquisitionCohortLedger` & `CustomerCohortRecord` (with backward-compatible aliases `ResponseCohortLedger` and `CohortRecord`).
   - `MediaResponseCohortLedger` & `MediaResponseCohortRecord` explicitly modeling spend, immediate response, carryover responses, adstock decay weights, and financial valuation (`gross_revenue`, `net_profit`, `roas`, `discounted_npv`).
3. **Ledger Engine**: Added `build_media_response_cohort_ledger` in `ledger.py` which consumes fitted adstock lag weights without duplicating adstock logic, enforces mass conservation, and provides `reconcile_to_calendar_response`.
4. **Unit Tests**: Added `TestMediaResponseCohortLedger` in `tests/unit/test_cohort_ledger.py` with 4 new tests.

### Verification
1. `uv run pytest tests/unit/test_cohort_ledger.py -v` passes 9/9 tests.
2. Verified mass conservation: $\text{immediate} + \sum \text{carryover} == \text{cumulative}$.
3. Verified calendar aggregate reconciliation across multiple source periods.

### Prevention rule
> **Never build generic 'cohort' domain abstractions across different business entities. Customer acquisition cohorts (CLV) and media response cohorts (MMM) must have separate schemas, units, and reconciliation targets.**

### Related code
- `src/marketing_mcp/domain/cohorts/contracts.py`
- `src/marketing_mcp/domain/cohorts/ledger.py`
- `docs/rfcs/003-media-response-cohort-accounting.md`

### Related tests
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger`
- `tests/unit/test_cohort_ledger.py::TestCustomerAcquisitionCohortLedger`

### Related lessons
- [06-bayesian-rfm-domain-invariants.md](./06-bayesian-rfm-domain-invariants.md)
- [12-saturation-curves-response-fidelity-and-decision-caveats.md](./12-saturation-curves-response-fidelity-and-decision-caveats.md)

### Status
Resolved
