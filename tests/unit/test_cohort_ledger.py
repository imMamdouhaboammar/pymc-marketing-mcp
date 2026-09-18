"""Unit tests for Response Cohort Ledger (T7).

Fast tests — zero sampling required.
Requirements:
- Aggregate totals reconcile to cohort sums within tolerance
- Missing cohort periods are explicitly identified
- Observational lag and maturity curves computed accurately
- Tenant isolation
- Zero faked customer records
"""

from __future__ import annotations

import pandas as pd
import pytest

from marketing_mcp.domain.cohorts import (
    ResponseCohortLedger,
    build_cohort_ledger,
    extract_cohorts_from_transactions,
)


class TestResponseCohortLedger:
    def test_reconciliation_within_numerical_tolerance(self):
        cohort_data = [
            {
                "acquisition_period": "2025-W01",
                "period_revenues": [1000.0, 300.0, 100.0],  # Total: 1400.0
            },
            {
                "acquisition_period": "2025-W02",
                "period_revenues": [1500.0, 500.0, 200.0],  # Total: 2200.0
            },
        ]
        ledger = build_cohort_ledger(cohort_data, tenant_id="tenant_1")
        assert ledger.total_cohort_revenue() == pytest.approx(3600.0)

        # Aggregate series matching cohort totals exactly
        aggregate = {
            "2025-W01": 1400.0,
            "2025-W02": 2200.0,
        }
        res = ledger.reconcile_to_aggregate(aggregate, tolerance=0.01)
        assert res["is_reconciled"] is True
        assert res["absolute_discrepancy"] == 0.0
        assert res["missing_cohort_periods"] == []

    def test_missing_cohort_periods_explicitly_flagged(self):
        cohort_data = [
            {"acquisition_period": "2025-W01", "period_revenues": [1000.0]},
            # Missing 2025-W02
            {"acquisition_period": "2025-W03", "period_revenues": [1200.0]},
        ]
        ledger = build_cohort_ledger(cohort_data)
        aggregate = {
            "2025-W01": 1000.0,
            "2025-W02": 1500.0,
            "2025-W03": 1200.0,
        }
        res = ledger.reconcile_to_aggregate(aggregate)
        assert "2025-W02" in res["missing_cohort_periods"]
        assert res["is_reconciled"] is False

    def test_maturity_curve_and_observational_lag(self):
        cohort_data = [
            {
                "acquisition_period": "2025-W01",
                # Rev: 600 at t0 (60%), 300 at t1 (90%), 100 at t2 (100%)
                "period_revenues": [600.0, 300.0, 100.0],
            }
        ]
        ledger = build_cohort_ledger(cohort_data)
        c = ledger.cohorts[0]
        assert c.cumulative_revenue == 1000.0
        assert c.maturity_curve == [0.6, 0.9, 1.0]
        assert c.observational_lag_periods == 2  # Reaches 95% at index 2 (1.0 >= 0.95)

    def test_extract_cohorts_from_transactions(self):
        # 3 customers over 3 weeks
        df = pd.DataFrame({
            "customer_id": ["c1", "c1", "c2", "c3"],
            "date": ["2025-01-06", "2025-01-13", "2025-01-06", "2025-01-13"],
            "amount": [100.0, 50.0, 200.0, 300.0],
        })
        ledger = extract_cohorts_from_transactions(
            df,
            customer_id_col="customer_id",
            date_col="date",
            value_col="amount",
            tenant_id="client_corp",
        )
        assert isinstance(ledger, ResponseCohortLedger)
        assert ledger.tenant_id == "client_corp"
        assert len(ledger.cohorts) == 2
        # c1 and c2 acquired in first week: amount = 100 + 200 = 300 in t0, c1 spent 50 in t1
        # c3 acquired in second week: amount = 300
        assert ledger.total_cohort_revenue() == 650.0
