"""Domain contracts for Response Cohort Ledger (T7).

Tracks commercial outcome realizations by acquisition cohort, maturity curves,
and observational lag. Reconciles cohort contributions with aggregate MMM target series.

Key invariant: Never fakes individual customer-level microdata when only aggregate/cohort data exists.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

PeriodType = Literal["daily", "weekly", "monthly"]


class CohortRecord(BaseModel):
    """Realization history and maturity progression for an acquisition cohort."""

    cohort_id: str = Field(description="Unique cohort identifier, e.g. '2025-W01' or '2025-01'")
    acquisition_period: str = Field(description="Calendar period when cohort was acquired")
    channel: str | None = Field(default=None, description="Acquiring channel if attributed")
    acquired_customers: int | None = Field(
        default=None, ge=0, description="Customer count in this cohort"
    )
    period_revenues: list[float] = Field(
        default_factory=list,
        description="Revenue realized in each subsequent period (t+0, t+1, t+2, ...)",
    )
    cumulative_revenue: float = Field(
        default=0.0, ge=0.0, description="Total cumulative revenue realized to date"
    )
    maturity_curve: list[float] = Field(
        default_factory=list,
        description="Empirical maturity fraction per lag period (cumulative revenue / mature revenue)",
    )
    observational_lag_periods: int = Field(
        default=0, ge=0, description="Number of periods until this cohort reaches 95% mature value"
    )
    provenance: dict[str, Any] = Field(default_factory=dict)


class ResponseCohortLedger(BaseModel):
    """Tenant-scoped ledger of acquisition cohorts and maturity progressions."""

    ledger_id: str = Field(description="Unique cohort ledger ID")
    tenant_id: str = Field(default="default", description="Tenant/organization identifier")
    project_id: str | None = Field(default=None, description="Optional project identifier")
    target_metric: str = Field(default="revenue", description="Outcome metric tracked in ledger")
    period_type: PeriodType = Field(default="weekly", description="Temporal granularity")
    cohorts: list[CohortRecord] = Field(default_factory=list, description="Collection of cohort records")
    metadata: dict[str, Any] = Field(default_factory=dict)

    def total_cohort_revenue(self) -> float:
        """Sum of cumulative revenue across all cohorts."""
        return sum(c.cumulative_revenue for c in self.cohorts)

    def reconcile_to_aggregate(
        self,
        aggregate_series: dict[str, float],
        tolerance: float = 0.05,
    ) -> dict[str, Any]:
        """Reconcile calendar-period aggregate outcomes against cohort contributions.

        Parameters
        ----------
        aggregate_series:
            Mapping of calendar period (e.g. '2025-01-06') to aggregate outcome observed.
        tolerance:
            Acceptable relative difference threshold (e.g. 5%).

        Returns
        -------
        dict with reconciliation status, discrepancies, and coverage.
        """
        cohort_calendar_totals: dict[str, float] = {}

        for c in self.cohorts:
            # Each subsequent period realized corresponds to an offset
            for offset, rev in enumerate(c.period_revenues):
                # For simplified reconciliation, group by acquisition + offset key
                key = f"{c.acquisition_period}+{offset}"
                cohort_calendar_totals[key] = cohort_calendar_totals.get(key, 0.0) + rev

        total_cohort_sum = sum(c.cumulative_revenue for c in self.cohorts)
        total_aggregate_sum = sum(aggregate_series.values()) if aggregate_series else 0.0

        diff = abs(total_cohort_sum - total_aggregate_sum)
        rel_diff = diff / max(1e-6, total_aggregate_sum) if total_aggregate_sum > 0 else 0.0
        is_reconciled = rel_diff <= tolerance

        return {
            "total_cohort_sum": round(total_cohort_sum, 2),
            "total_aggregate_sum": round(total_aggregate_sum, 2),
            "absolute_discrepancy": round(diff, 2),
            "relative_discrepancy_pct": round(rel_diff * 100, 2),
            "is_reconciled": is_reconciled,
            "cohort_count": len(self.cohorts),
            "missing_cohort_periods": [
                p for p in aggregate_series if not any(c.acquisition_period == p for c in self.cohorts)
            ],
        }
