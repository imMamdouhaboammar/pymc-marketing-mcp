# Lesson 64: Unvalidated Financial Assumptions in Decision Builders

### Context
Financial valuation contracts across decision tools and cohort accounting (`src/marketing_mcp/domain/decisions/financial.py`, `src/marketing_mcp/domain/cohorts/ledger.py`).

### What happened
`FinancialAssumptions` is the canonical dataclass representing margin rates, discount rates, revenue scaling, and variable costs for financial decisions. It provides a formal `validate() -> list[str]` method checking that:
- $0.0 \le \text{gross\_margin\_rate} \le 1.0$
- $0.0 \le \text{discount\_rate} \le 1.0$
- $\text{revenue\_per\_outcome} \ge 0.0$

However, `build_media_response_cohort_ledger` accepted an optional `financial: FinancialAssumptions` instance and passed its fields directly to `record.evaluate_financials(...)` without invoking `financial.validate()`.

An invalid assumptions object (e.g. `gross_margin_rate=1.5` or `discount_rate=-0.20`) passed silently into cohort financial calculations, producing corrupt net profit and discounted NPV metrics without warning.

### Why it mattered / Impact
Downstream optimization workflows, scenario planners, and executive reporting rely on discounted net present value (NPV) and profit metrics. Unchecked margins $>100\%$ or negative discount rates inflate economic returns and lead to irresponsible marketing budget allocation.

### Observable symptom
A test constructing a media cohort with `FinancialAssumptions(gross_margin_rate=1.5)` successfully returned financial metrics showing a $150\%$ margin rather than raising an input validation error.

### Incorrect assumption
Assumed that because `FinancialAssumptions` was an instantiated typed dataclass, validation had already been performed at creation time.

### Root cause
**Confirmed**. In Python, dataclasses (even `frozen=True`) do not enforce validation at instantiation unless explicit post-init checks or validation methods are called. Calling code assumed validation had happened upstream, creating an intake validation gap.

### Why the system allowed it
`FinancialAssumptions` used deferred validation via an explicit `validate()` method rather than a Pydantic model with eager validators, but the caller in `ledger.py` neglected to invoke that method.

### Fix
1. Explicitly invoke `financial.validate()` at the entrance of `build_media_response_cohort_ledger`.
2. If `fin_errors` is non-empty, immediately raise `DomainError("INPUT_INVALID", f"Invalid financial assumptions: {'; '.join(fin_errors)}")`.
3. In `MediaResponseCohortRecord._synchronize_responses`, enforce that response components are non-negative and dual representations (`period_responses` vs `immediate_response` + `carryover_responses`) are mathematically consistent.

### Verification
Added `test_reject_invalid_financial_assumptions` in `tests/unit/test_cohort_ledger.py`:
- Asserts that `FinancialAssumptions(gross_margin_rate=1.5)` raises `DomainError` with code `INPUT_INVALID`.
- 18/18 unit tests in `tests/unit/test_cohort_ledger.py` passing.

### Prevention rule
> **Every domain builder consuming contracts with deferred validation methods (`validate()`) must explicitly invoke and assert validity at the boundary before executing downstream calculations.**

### Reusable lesson
Applies to all contracts using deferred validation across the platform. Where contracts cannot use eager Pydantic validation (e.g., frozen dataclasses shared across performance-critical paths), consumption boundaries must treat `.validate()` as mandatory before using contract attributes.

### Related code
- `src/marketing_mcp/domain/decisions/financial.py`
- `src/marketing_mcp/domain/cohorts/ledger.py`
- `src/marketing_mcp/domain/cohorts/contracts.py`

### Related tests
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger::test_reject_invalid_financial_assumptions`
- `tests/unit/test_financial_assumptions.py`

### Related lessons
- [18-silent-sqlite-cleanup-syntax-error.md](./18-silent-sqlite-cleanup-syntax-error.md)
- [46-bogus-provenance-acceptance-on-uncalibrated-confidence.md](./46-bogus-provenance-acceptance-on-uncalibrated-confidence.md)
- [48-registry-negative-guards-and-rfc-gated-objectives.md](./48-registry-negative-guards-and-rfc-gated-objectives.md)

### Status
Resolved
