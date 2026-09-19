# Lesson 62: Period-by-Period Reconciliation vs Grand Total Conservation Drift

### Context
Temporal carryover response cohort reconciliation in `MediaResponseCohortLedger.reconcile_to_calendar_response` (`src/marketing_mcp/domain/cohorts/contracts.py`).

### What happened
The initial implementation of `reconcile_to_calendar_response` computed only the aggregate grand total across all calendar periods:
$$\text{diff} = \left| \sum_{p} c_p - \sum_{p} y_p \right|$$

When evaluated against a calendar response series where timing shifts occurred (e.g., source cohorts produced $+200$ in period $W01$ and $-200$ in period $W02$ relative to authoritative measurements), the errors canceled out perfectly in the grand total. The system reported `is_reconciled = True` with $0.0$ discrepancy.

Furthermore, when authoritative response was $0.0$ for an evaluated period or series but cohorts produced non-zero carryover responses, the division:
```python
rel_diff = diff / max(1e-6, total_authoritative_sum) if total_authoritative_sum > 0 else 0.0
```
evaluated `rel_diff` as $0.0$, falsely certifying a severe discrepancy as reconciled.

### Why it mattered / Impact
Econometricians and marketing decision-makers use media cohort ledgers to verify that adstock carryover parameters faithfully reproduce calendar-period marketing impact. When temporal timing shifts are hidden by grand-total aggregation:
1. Short-term and long-term marketing effects are conflated.
2. Budget flighting optimization tools misallocate spend across temporal horizons.
3. Zero-target periods containing spurious model carryovers are certified as accurate.

### Observable symptom
An adversarial test with $+200$ in week 1 and $-200$ in week 2 passed reconciliation. An authoritative calendar series with $0.0$ response passed reconciliation despite cohorts generating $100.0$ response units.

### Incorrect assumption
Assumed that overall mass conservation ($\sum c_p == \sum y_p$) was a sufficient condition to certify distributed lag fidelity across time.

### Root cause
**Confirmed**. Grand-total aggregation collapses the temporal dimension, blinding the validation gate to compensating timing shifts across individual evaluation intervals. Additionally, the zero-denominator guard defaulted to $0.0$ relative error rather than failing closed on non-zero absolute difference.

### Why the system allowed it
Initial test fixtures used synthetic data where both grand totals and individual periods matched exactly, masking the blind spot in the reconciliation logic.

### Fix
1. **Period-by-Period Check**: Added iteration across each period $p \in \text{calendar\_responses}$, evaluating period-level difference $p_{\text{diff}} = |c_p - y_p|$ against `tolerance`.
2. **Zero-Target Handling**: If $y_p == 0.0$, require $p_{\text{diff}} == 0.0$; any non-zero cohort response yields $p_{\text{rel}} = 1.0$ and fails period reconciliation.
3. **Discrepancy Reporting**: Return `discrepant_periods: list[str]` and `period_details: dict[str, Any]` exposing period-level drift.
4. **Joint Verdict**:
   ```python
   is_reconciled = grand_reconciled and (len(discrepant_periods) == 0)
   ```

### Verification
1. `test_period_by_period_reconciliation_catches_timing_shift`: Verifies that compensating errors across W01 and W02 produce `is_reconciled = False` with `discrepant_periods = ['2025-W01', '2025-W02']`.
2. `test_reconciliation_fails_when_authoritative_response_is_zero`: Verifies that a zero authoritative response with non-zero cohort response produces `is_reconciled = False`.
3. 18/18 unit tests in `tests/unit/test_cohort_ledger.py` passing.

### Prevention rule
> **Never validate distributed lag or time-series allocations using grand-total sums alone. Time-series reconciliation must enforce period-by-period tolerance thresholds and fail closed on zero-target discrepancies.**

### Reusable lesson
Applies to all time-series and allocation reconciliation in marketing mix modeling, attribution models, budget flighting, and financial revenue recognition. Whenever carryover or decay is distributed across intervals, validation must inspect each interval individually.

### Related code
- `src/marketing_mcp/domain/cohorts/contracts.py`
- `src/marketing_mcp/domain/cohorts/ledger.py`

### Related tests
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger::test_period_by_period_reconciliation_catches_timing_shift`
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger::test_reconciliation_fails_when_authoritative_response_is_zero`

### Related lessons
- [39-statistical-test-assertion-drift-and-budget-conservation.md](./39-statistical-test-assertion-drift-and-budget-conservation.md)
- [47-conflation-of-media-response-and-customer-acquisition-cohorts.md](./47-conflation-of-media-response-and-customer-acquisition-cohorts.md)

### Status
Resolved

## Signed and non-finite authoritative inputs

Period-level reconciliation must validate the authoritative series before computing relative error. For response/count-like domains whose modeled contributions are constrained non-negative, reject negative, NaN, and infinite authoritative values instead of letting signed denominators or non-finite arithmetic participate in tolerance checks. A conservation check is not meaningful when the comparison domain itself violates its contract.
