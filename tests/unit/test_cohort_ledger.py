"""Unit tests for Customer Acquisition and Media Response Cohort Ledgers (T7 & RFC 003).

Fast tests — zero sampling required.
Requirements:
- Customer acquisition totals reconcile to cohort sums within tolerance
- Missing cohort periods are explicitly identified
- Observational lag and maturity curves computed accurately
- Media source-period response cohorts decompose into immediate (t+0) and carryover (t+1..t+L)
- Conservation of media response mass: immediate + sum(carryover) == cumulative
- Media response reconciliation against calendar-period aggregate response
- Financial valuation of media response cohorts (gross revenue, net profit, ROAS, NPV)
- Semantic separation: CustomerCohortRecord vs MediaResponseCohortRecord
- Tenant isolation
- Zero faked customer records
"""

from __future__ import annotations

import pandas as pd
import pytest
from pydantic import ValidationError

from marketing_mcp.domain.cohorts import (
    CohortRecord,
    CustomerAcquisitionCohortLedger,
    CustomerCohortRecord,
    MediaResponseCohortLedger,
    MediaResponseCohortRecord,
    ResponseCohortLedger,
    build_cohort_ledger,
    build_media_response_cohort_ledger,
    extract_cohorts_from_transactions,
)
from marketing_mcp.domain.decisions.financial import FinancialAssumptions
from marketing_mcp.errors import DomainError


class TestCustomerAcquisitionCohortLedger:
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
        df = pd.DataFrame(
            {
                "customer_id": ["c1", "c1", "c2", "c3"],
                "date": ["2025-01-06", "2025-01-13", "2025-01-06", "2025-01-13"],
                "amount": [100.0, 50.0, 200.0, 300.0],
            }
        )
        ledger = extract_cohorts_from_transactions(
            df,
            customer_id_col="customer_id",
            date_col="date",
            value_col="amount",
            tenant_id="client_corp",
        )
        assert isinstance(ledger, CustomerAcquisitionCohortLedger)
        assert isinstance(ledger, ResponseCohortLedger)  # alias
        assert ledger.tenant_id == "client_corp"
        assert len(ledger.cohorts) == 2
        # c1 and c2 acquired in first week: amount = 100 + 200 = 300 in t0, c1 spent 50 in t1
        # c3 acquired in second week: amount = 300
        assert ledger.total_cohort_revenue() == 650.0

    def test_backward_compatible_aliases(self):
        assert CustomerCohortRecord is CohortRecord
        assert CustomerAcquisitionCohortLedger is ResponseCohortLedger


class TestMediaResponseCohortLedger:
    def test_media_cohort_decomposition_immediate_and_carryover(self):
        spend_records = [
            {
                "source_period": "2025-W01",
                "channel": "tv",
                "spend": 10000.0,
                "total_response": 2000.0,
            }
        ]
        # Adstock weights: 50% lag 0, 30% lag 1, 20% lag 2
        adstock_weights = {"tv": [0.5, 0.3, 0.2]}

        ledger = build_media_response_cohort_ledger(
            spend_records=spend_records,
            adstock_weights=adstock_weights,
            tenant_id="org_alpha",
        )
        assert isinstance(ledger, MediaResponseCohortLedger)

        assert len(ledger.cohorts) == 1
        cohort = ledger.cohorts[0]
        assert isinstance(cohort, MediaResponseCohortRecord)
        assert cohort.channel == "tv"
        assert cohort.source_period == "2025-W01"
        assert cohort.spend == 10000.0
        # Immediate response (t+0): 2000 * 0.5 = 1000
        assert cohort.immediate_response == pytest.approx(1000.0)
        # Carryover responses (t+1, t+2): [600.0, 400.0]
        assert cohort.carryover_responses == [pytest.approx(600.0), pytest.approx(400.0)]
        assert cohort.period_responses == [
            pytest.approx(1000.0),
            pytest.approx(600.0),
            pytest.approx(400.0),
        ]
        assert cohort.cumulative_response == pytest.approx(2000.0)

    def test_conservation_of_response_mass(self):
        spend_records = [
            {"source_period": "2025-W01", "channel": "search", "spend": 5000.0},
            {"source_period": "2025-W02", "channel": "search", "spend": 8000.0},
        ]
        adstock_weights = {"search": [0.7, 0.2, 0.1]}
        # 1.5 responses per dollar
        channel_rates = {"search": 1.5}

        ledger = build_media_response_cohort_ledger(
            spend_records=spend_records,
            adstock_weights=adstock_weights,
            channel_response_rates=channel_rates,
        )

        for c in ledger.cohorts:
            assert c.immediate_response + sum(c.carryover_responses) == pytest.approx(
                c.cumulative_response
            )
            assert sum(c.period_responses) == pytest.approx(c.cumulative_response)

        assert ledger.total_spend() == pytest.approx(13000.0)
        assert ledger.total_response() == pytest.approx(13000.0 * 1.5)
        assert ledger.total_immediate_response() == pytest.approx(13000.0 * 1.5 * 0.7)
        assert ledger.total_carryover_response() == pytest.approx(13000.0 * 1.5 * 0.3)

    def test_reconcile_to_calendar_response(self):
        # Two consecutive weeks of spend
        # W01: spend produces 1000 total (600 at W01, 300 at W02, 100 at W03)
        # W02: spend produces 2000 total (1200 at W02, 600 at W03, 200 at W04)
        spend_records = [
            {
                "source_period": "2025-W01",
                "channel": "meta",
                "spend": 1000.0,
                "total_response": 1000.0,
            },
            {
                "source_period": "2025-W02",
                "channel": "meta",
                "spend": 2000.0,
                "total_response": 2000.0,
            },
        ]
        adstock_weights = {"meta": [0.6, 0.3, 0.1]}

        ledger = build_media_response_cohort_ledger(spend_records, adstock_weights)

        # Authoritative calendar aggregate:
        # W01: 600 (W01 lag 0)
        # W02: 300 (W01 lag 1) + 1200 (W02 lag 0) = 1500
        # W03: 100 (W01 lag 2) + 600 (W02 lag 1) = 700
        # W04: 200 (W02 lag 2) = 200
        calendar_series = {
            "2025-W01": 600.0,
            "2025-W02": 1500.0,
            "2025-W03": 700.0,
            "2025-W04": 200.0,
        }

        recon = ledger.reconcile_to_calendar_response(calendar_series, tolerance=0.01)
        assert recon["is_reconciled"] is True
        assert recon["absolute_discrepancy"] == pytest.approx(0.0)
        assert recon["total_authoritative_sum"] == pytest.approx(3000.0)
        assert recon["total_cohort_calendar_sum"] == pytest.approx(3000.0)

    def test_financial_valuation_with_assumptions(self):
        spend_records = [
            {
                "source_period": "2025-W01",
                "channel": "tv",
                "spend": 10000.0,
                "total_response": 500.0,
            }
        ]
        adstock_weights = {"tv": [0.5, 0.5]}  # 250 at t0, 250 at t1
        # revenue_per_outcome = 50.0 (each response unit is $50)
        # gross margin = 0.60
        # discount rate = 0.10 (10% periodic discount)
        fa = FinancialAssumptions(
            revenue_per_outcome=50.0,
            gross_margin_rate=0.60,
            discount_rate=0.10,
        )

        ledger = build_media_response_cohort_ledger(
            spend_records=spend_records,
            adstock_weights=adstock_weights,
            financial=fa,
        )

        cohort = ledger.cohorts[0]
        # Total response = 500
        # Gross revenue = 500 * 50 = $25,000
        # Net profit = 25,000 * 0.60 - 10,000 = 15,000 - 10,000 = $5,000
        # ROAS = 25,000 / 10,000 = 2.50
        # NPV:
        # t0: (250 * 50 * 0.6) / (1.0)^0 = 7500
        # t1: (250 * 50 * 0.6) / (1.1)^1 = 7500 / 1.1 = 6818.18
        # NPV = 7500 + 6818.18 - 10000 = 4318.18
        val = cohort.financial_valuation
        assert val["gross_revenue"] == pytest.approx(25000.0)
        assert val["net_profit"] == pytest.approx(5000.0)
        assert val["roas"] == pytest.approx(2.50)
        assert val["discounted_npv"] == pytest.approx(4318.18, rel=1e-2)

    def test_reject_missing_response_and_rate(self):
        spend_records = [{"source_period": "2025-W01", "channel": "tv", "spend": 5000.0}]
        adstock_weights = {"tv": [0.5, 0.5]}
        with pytest.raises(DomainError) as exc_info:
            build_media_response_cohort_ledger(spend_records, adstock_weights)
        assert exc_info.value.code == "INPUT_INVALID"
        assert "Missing total_response or channel_response_rate" in str(exc_info.value)

    def test_reject_channel_not_in_adstock_weights(self):
        spend_records = [
            {"source_period": "2025-W01", "channel": "meta", "spend": 5000.0, "total_response": 200.0}
        ]
        adstock_weights = {"tv": [0.5, 0.5]}  # missing "meta"
        with pytest.raises(DomainError) as exc_info:
            build_media_response_cohort_ledger(spend_records, adstock_weights)
        assert exc_info.value.code == "INPUT_INVALID"
        assert "Missing adstock weights for channel 'meta'" in str(exc_info.value)

    def test_reject_invalid_adstock_weights(self):
        spend_records = [
            {"source_period": "2025-W01", "channel": "tv", "spend": 1000.0, "total_response": 100.0}
        ]
        # Empty weights
        with pytest.raises(DomainError) as exc_info:
            build_media_response_cohort_ledger(spend_records, {"tv": []})
        assert exc_info.value.code == "INPUT_INVALID"

        # Negative weights
        with pytest.raises(DomainError) as exc_info:
            build_media_response_cohort_ledger(spend_records, {"tv": [0.8, -0.2]})
        assert exc_info.value.code == "INPUT_INVALID"

        # Zero sum weights
        with pytest.raises(DomainError) as exc_info:
            build_media_response_cohort_ledger(spend_records, {"tv": [0.0, 0.0]})
        assert exc_info.value.code == "INPUT_INVALID"

    def test_reject_duplicate_cohort_records(self):
        spend_records = [
            {"source_period": "2025-W01", "channel": "tv", "spend": 1000.0, "total_response": 100.0},
            {"source_period": "2025-W01", "channel": "tv", "spend": 2000.0, "total_response": 200.0},
        ]
        adstock_weights = {"tv": [0.6, 0.4]}
        with pytest.raises(DomainError) as exc_info:
            build_media_response_cohort_ledger(spend_records, adstock_weights)
        assert exc_info.value.code == "INPUT_INVALID"
        assert "Duplicate spend record" in str(exc_info.value)

    def test_reject_invalid_financial_assumptions(self):
        spend_records = [
            {"source_period": "2025-W01", "channel": "tv", "spend": 1000.0, "total_response": 100.0}
        ]
        adstock_weights = {"tv": [0.5, 0.5]}
        # Invalid gross margin rate > 1.0
        fa = FinancialAssumptions(gross_margin_rate=1.5)
        with pytest.raises(DomainError) as exc_info:
            build_media_response_cohort_ledger(spend_records, adstock_weights, financial=fa)
        assert exc_info.value.code == "INPUT_INVALID"
        assert "Invalid financial assumptions" in str(exc_info.value)

    def test_record_validation_rejects_negative_responses(self):
        with pytest.raises(ValidationError):
            MediaResponseCohortRecord(
                cohort_id="c1",
                source_period="2025-W01",
                channel="tv",
                spend=100.0,
                period_responses=[100.0, -20.0],
            )

    def test_record_validation_rejects_conflicting_representations(self):
        with pytest.raises(ValidationError):
            MediaResponseCohortRecord(
                cohort_id="c1",
                source_period="2025-W01",
                channel="tv",
                spend=100.0,
                immediate_response=50.0,
                carryover_responses=[50.0],
                period_responses=[100.0, 50.0],  # 100 != 50
            )

    def test_period_by_period_reconciliation_catches_timing_shift(self):
        # Two weeks of spend where grand total matches (3000 vs 3000)
        # but timing differs period by period
        spend_records = [
            {"source_period": "2025-W01", "channel": "meta", "spend": 1000.0, "total_response": 1000.0},
            {"source_period": "2025-W02", "channel": "meta", "spend": 2000.0, "total_response": 2000.0},
        ]
        adstock_weights = {"meta": [0.6, 0.3, 0.1]}
        ledger = build_media_response_cohort_ledger(spend_records, adstock_weights)

        # Expected cohort totals:
        # W01: 600, W02: 1500, W03: 700, W04: 200 (Total: 3000)
        # Shifted authoritative series:
        # W01: 800 (+200), W02: 1300 (-200), W03: 700, W04: 200 (Total: 3000)
        shifted_calendar = {
            "2025-W01": 800.0,
            "2025-W02": 1300.0,
            "2025-W03": 700.0,
            "2025-W04": 200.0,
        }
        recon = ledger.reconcile_to_calendar_response(shifted_calendar, tolerance=0.01)
        # Grand total discrepancy is 0, but period-by-period fails!
        assert recon["absolute_discrepancy"] == pytest.approx(0.0)
        assert recon["is_reconciled"] is False
        assert "2025-W01" in recon["discrepant_periods"]
        assert "2025-W02" in recon["discrepant_periods"]

    def test_reconciliation_fails_when_authoritative_response_is_zero(self):
        spend_records = [
            {"source_period": "2025-W01", "channel": "tv", "spend": 1000.0, "total_response": 100.0}
        ]
        adstock_weights = {"tv": [1.0]}
        ledger = build_media_response_cohort_ledger(spend_records, adstock_weights)

        # Authoritative response says zero, but cohorts produced 100
        zero_calendar = {"2025-W01": 0.0}
        recon = ledger.reconcile_to_calendar_response(zero_calendar, tolerance=0.05)
        assert recon["is_reconciled"] is False
        assert recon["total_authoritative_sum"] == 0.0
        assert recon["total_cohort_calendar_sum"] == pytest.approx(100.0)
        assert "2025-W01" in recon["discrepant_periods"]

    def test_reconciliation_rejects_negative_authoritative_response(self):
        spend_records = [
            {"source_period": "2025-W01", "channel": "tv", "spend": 1000.0, "total_response": 100.0}
        ]
        adstock_weights = {"tv": [1.0]}
        ledger = build_media_response_cohort_ledger(spend_records, adstock_weights)

        # A negative authoritative period must fail closed instead of producing
        # a negative relative discrepancy that could be certified as reconciled.
        with pytest.raises(ValueError, match="must be non-negative"):
            ledger.reconcile_to_calendar_response(
                {"2025-W01": -5.0, "2025-W02": 105.0},
                tolerance=0.05,
                period_order=["2025-W01", "2025-W02"],
            )

    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_reconciliation_rejects_non_finite_authoritative_response(self, bad_value):
        spend_records = [
            {"source_period": "2025-W01", "channel": "tv", "spend": 1000.0, "total_response": 100.0}
        ]
        ledger = build_media_response_cohort_ledger(spend_records, {"tv": [1.0]})

        with pytest.raises(ValueError, match="must be finite"):
            ledger.reconcile_to_calendar_response({"2025-W01": bad_value})

    @pytest.mark.parametrize("bad_tolerance", [-0.01, float("nan"), float("inf")])
    def test_reconciliation_rejects_invalid_tolerance(self, bad_tolerance):
        spend_records = [
            {"source_period": "2025-W01", "channel": "tv", "spend": 1000.0, "total_response": 100.0}
        ]
        ledger = build_media_response_cohort_ledger(spend_records, {"tv": [1.0]})

        with pytest.raises(ValueError, match="tolerance must be a finite non-negative number"):
            ledger.reconcile_to_calendar_response(
                {"2025-W01": 100.0},
                tolerance=bad_tolerance,
            )


    @pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), float("-inf")])
    def test_record_validation_rejects_non_finite_response_components(self, bad_value):
        with pytest.raises(ValidationError, match="non-finite|finite"):
            MediaResponseCohortRecord(
                cohort_id="c-nonfinite",
                source_period="2025-W01",
                channel="tv",
                spend=100.0,
                period_responses=[bad_value],
            )

        with pytest.raises(ValidationError, match="non-finite|finite"):
            MediaResponseCohortRecord(
                cohort_id="c-weight-nonfinite",
                source_period="2025-W01",
                channel="tv",
                spend=100.0,
                period_responses=[100.0],
                adstock_decay_weights=[bad_value],
            )

    def test_record_validation_rejects_zero_sum_adstock_weights(self):
        with pytest.raises(ValidationError, match="sum to > 0"):
            MediaResponseCohortRecord(
                cohort_id="c-zero-weights",
                source_period="2025-W01",
                channel="tv",
                spend=100.0,
                period_responses=[100.0],
                adstock_decay_weights=[0.0, 0.0],
            )

    def test_reconciliation_rejects_empty_authoritative_series(self):
        ledger = build_media_response_cohort_ledger(
            [
                {
                    "source_period": "2025-W01",
                    "channel": "tv",
                    "spend": 1000.0,
                    "total_response": 100.0,
                }
            ],
            {"tv": [1.0]},
        )

        with pytest.raises(
            ValueError,
            match="calendar_responses must contain at least one authoritative period",
        ):
            ledger.reconcile_to_calendar_response({})

    def test_reconciliation_fails_when_carryover_falls_outside_authoritative_window(self):
        ledger = build_media_response_cohort_ledger(
            [
                {
                    "source_period": "2025-W01",
                    "channel": "tv",
                    "spend": 1000.0,
                    "total_response": 100.0,
                }
            ],
            {"tv": [0.0, 1.0]},
        )

        # The authoritative window only covers W01. The full modeled response is
        # carried into the next period and must not be silently dropped.
        recon = ledger.reconcile_to_calendar_response({"2025-W01": 0.0})
        assert recon["is_reconciled"] is False
        assert recon["unmapped_response_total"] == pytest.approx(100.0)
        assert recon["unmapped_cohort_ids"] == [ledger.cohorts[0].cohort_id]

    def test_reconciliation_fails_when_period_order_contains_uncovered_response_period(self):
        ledger = build_media_response_cohort_ledger(
            [
                {
                    "source_period": "2025-W01",
                    "channel": "tv",
                    "spend": 1000.0,
                    "total_response": 100.0,
                }
            ],
            {"tv": [0.5, 0.5]},
        )

        recon = ledger.reconcile_to_calendar_response(
            {"2025-W01": 50.0},
            period_order=["2025-W01", "2025-W02"],
        )
        assert recon["is_reconciled"] is False
        assert recon["unmapped_response_total"] == pytest.approx(50.0)
        assert recon["uncovered_periods"] == ["2025-W02"]

    def test_reconciliation_rejects_invalid_period_order(self):
        ledger = build_media_response_cohort_ledger(
            [
                {
                    "source_period": "2025-W01",
                    "channel": "tv",
                    "spend": 1000.0,
                    "total_response": 100.0,
                }
            ],
            {"tv": [1.0]},
        )

        with pytest.raises(ValueError, match="cannot be empty"):
            ledger.reconcile_to_calendar_response(
                {"2025-W01": 100.0},
                period_order=[],
            )

        with pytest.raises(ValueError, match="duplicate periods"):
            ledger.reconcile_to_calendar_response(
                {"2025-W01": 100.0},
                period_order=["2025-W01", "2025-W01"],
            )

        with pytest.raises(ValueError, match="missing authoritative period"):
            ledger.reconcile_to_calendar_response(
                {"2025-W01": 100.0},
                period_order=["2025-W02"],
            )


def test_media_record_rejects_hidden_cumulative_response_without_period_decomposition():
    with pytest.raises(
        ValidationError,
        match="cumulative_response cannot be positive without a period response decomposition",
    ):
        MediaResponseCohortRecord(
            cohort_id="hidden-mass",
            source_period="2025-W01",
            channel="tv",
            spend=100.0,
            cumulative_response=50.0,
        )


@pytest.mark.parametrize(
    ("period_type", "calendar_responses", "period_order"),
    [
        ("weekly", {"2025-W01": 50.0, "2025-W03": 50.0}, None),
        (
            "weekly",
            {"2025-W01": 50.0, "2025-W02": 50.0},
            ["2025-W02", "2025-W01"],
        ),
        ("daily", {"2025-01-01": 50.0, "2025-01-03": 50.0}, None),
        ("monthly", {"2025-01": 50.0, "2025-03": 50.0}, None),
    ],
)
def test_reconciliation_rejects_gapped_or_out_of_order_period_sequences(
    period_type, calendar_responses, period_order
):
    source_period = next(iter(calendar_responses))
    ledger = MediaResponseCohortLedger(
        ledger_id="ledger-period-order",
        period_type=period_type,
        cohorts=[
            MediaResponseCohortRecord(
                cohort_id="cohort-period-order",
                source_period=source_period,
                channel="tv",
                spend=100.0,
                period_responses=[50.0, 50.0],
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match="period_order must be chronological and contiguous",
    ):
        ledger.reconcile_to_calendar_response(
            calendar_responses,
            period_order=period_order,
        )


@pytest.mark.parametrize(
    ("period_type", "calendar_responses"),
    [
        ("weekly", {"2025-W01": 50.0, "2025-W02": 50.0}),
        ("daily", {"2025-01-01": 50.0, "2025-01-02": 50.0}),
        ("monthly", {"2025-01": 50.0, "2025-02": 50.0}),
    ],
)
def test_reconciliation_accepts_contiguous_period_sequences(period_type, calendar_responses):
    source_period = next(iter(calendar_responses))
    ledger = MediaResponseCohortLedger(
        ledger_id="ledger-contiguous-period-order",
        period_type=period_type,
        cohorts=[
            MediaResponseCohortRecord(
                cohort_id="cohort-contiguous-period-order",
                source_period=source_period,
                channel="tv",
                spend=100.0,
                period_responses=[50.0, 50.0],
            )
        ],
    )

    reconciliation = ledger.reconcile_to_calendar_response(calendar_responses)
    assert reconciliation["is_reconciled"] is True


@pytest.mark.parametrize(
    "bad_daily_period",
    [
        "2025-W01-1",
        "20250101",
        "2025-1-01",
        "2025-01-1",
    ],
)
def test_reconciliation_rejects_noncanonical_daily_period_labels(bad_daily_period):
    ledger = MediaResponseCohortLedger(
        ledger_id="ledger-daily-format",
        period_type="daily",
        cohorts=[
            MediaResponseCohortRecord(
                cohort_id="cohort-daily-format",
                source_period=bad_daily_period,
                channel="tv",
                spend=100.0,
                period_responses=[100.0],
            )
        ],
    )

    with pytest.raises(ValueError, match="invalid daily period label"):
        ledger.reconcile_to_calendar_response({bad_daily_period: 100.0})


def test_reconciliation_accepts_canonical_daily_period_labels():
    ledger = MediaResponseCohortLedger(
        ledger_id="ledger-daily-format-valid",
        period_type="daily",
        cohorts=[
            MediaResponseCohortRecord(
                cohort_id="cohort-daily-format-valid",
                source_period="2025-01-01",
                channel="tv",
                spend=100.0,
                period_responses=[50.0, 50.0],
            )
        ],
    )

    reconciliation = ledger.reconcile_to_calendar_response(
        {"2025-01-01": 50.0, "2025-01-02": 50.0}
    )
    assert reconciliation["is_reconciled"] is True
