"""Domain contracts for Customer Acquisition and Media Response Cohort Ledgers (T7 & RFC 003).

Distinguishes two fundamentally distinct cohort structures:
1. Customer Acquisition Cohorts (CLV): tracks cohort retention, maturity curve,
   and repeat transaction revenue over time from customer acquisition microdata.
2. Media Source-Period Response Cohorts (MMM): tracks marketing spend deployed at
   source period t, decomposing total response into immediate response (t+0) and
   carryover responses (t+1..t+L) via fitted adstock decay weights.

Key invariants:
- Never fakes individual customer microdata when only aggregate data exists.
- Never implements a second adstock system; consumes fitted posterior weights.
- Enforces reconciliation between source-period cohort carryovers and calendar aggregate response.
"""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

PeriodType = Literal["daily", "weekly", "monthly"]


def _period_ordinal(period: str, period_type: PeriodType) -> int:
    """Parse a supported period label into a monotonic unit ordinal."""
    if not isinstance(period, str) or not period:
        raise ValueError("period labels must be non-empty strings")

    try:
        if period_type == "daily":
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", period):
                raise ValueError
            return date.fromisoformat(period).toordinal()
        if period_type == "weekly":
            match = re.fullmatch(r"(\d{4})-W(\d{2})", period)
            if not match:
                raise ValueError
            year, week = (int(part) for part in match.groups())
            return date.fromisocalendar(year, week, 1).toordinal() // 7
        if period_type == "monthly":
            match = re.fullmatch(r"(\d{4})-(\d{2})", period)
            if not match:
                raise ValueError
            year, month = (int(part) for part in match.groups())
            if not 1 <= month <= 12:
                raise ValueError
            return year * 12 + (month - 1)
    except ValueError as exc:
        raise ValueError(
            f"invalid {period_type} period label '{period}'; expected "
            + (
                "YYYY-MM-DD"
                if period_type == "daily"
                else "YYYY-Www"
                if period_type == "weekly"
                else "YYYY-MM"
            )
        ) from exc

    raise ValueError(f"unsupported period_type '{period_type}'")


class CustomerCohortRecord(BaseModel):
    """Realization history and maturity progression for an acquisition cohort of customers."""

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


# Backward-compatible alias for existing callers
CohortRecord = CustomerCohortRecord


class CustomerAcquisitionCohortLedger(BaseModel):
    """Tenant-scoped ledger of customer acquisition cohorts and maturity progressions."""

    ledger_id: str = Field(description="Unique cohort ledger ID")
    tenant_id: str = Field(default="default", description="Tenant/organization identifier")
    project_id: str | None = Field(default=None, description="Optional project identifier")
    target_metric: str = Field(default="revenue", description="Outcome metric tracked in ledger")
    period_type: PeriodType = Field(default="weekly", description="Temporal granularity")
    cohorts: list[CustomerCohortRecord] = Field(
        default_factory=list, description="Collection of customer cohort records"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def total_cohort_revenue(self) -> float:
        """Sum of cumulative revenue across all cohorts."""
        return sum(c.cumulative_revenue for c in self.cohorts)

    def reconcile_to_aggregate(
        self,
        aggregate_series: dict[str, float],
        tolerance: float = 0.05,
    ) -> dict[str, Any]:
        """Reconcile calendar-period aggregate outcomes against cohort contributions."""
        cohort_calendar_totals: dict[str, float] = {}

        for c in self.cohorts:
            for offset, rev in enumerate(c.period_revenues):
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
                p
                for p in aggregate_series
                if not any(c.acquisition_period == p for c in self.cohorts)
            ],
        }


# Backward-compatible alias
ResponseCohortLedger = CustomerAcquisitionCohortLedger


class MediaResponseCohortRecord(BaseModel):
    """Media source-period response cohort (RFC 003).

    Tracks marketing spend deployed at source period t on a specific channel,
    decomposing its total outcome into immediate response (t+0) and carryover
    responses (t+1..t+L) governed by fitted adstock decay weights.
    """

    cohort_id: str = Field(description="Unique cohort identifier, e.g. 'media_2025-W01_tv'")
    source_period: str = Field(description="Calendar period when spend was deployed")
    channel: str = Field(description="Media channel")
    spend: float = Field(default=0.0, ge=0.0, description="Spend deployed in source period")
    immediate_response: float = Field(
        default=0.0, ge=0.0, description="Response realized at lag 0 (same period as spend)"
    )
    carryover_responses: list[float] = Field(
        default_factory=list,
        description="Carryover response realized at subsequent lags (t+1, t+2, ...)",
    )
    period_responses: list[float] = Field(
        default_factory=list,
        description="Complete response progression [immediate, carryover_1, carryover_2, ...]",
    )
    cumulative_response: float = Field(
        default=0.0, ge=0.0, description="Total lifetime response generated across all lags"
    )
    adstock_decay_weights: list[float] = Field(
        default_factory=list,
        description="Normalized adstock weights used for temporal decomposition",
    )
    financial_valuation: dict[str, float] = Field(
        default_factory=dict,
        description="Financial valuation metrics (gross_revenue, net_profit, roas, discounted_npv)",
    )
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _synchronize_responses(self) -> "MediaResponseCohortRecord":
        scalar_values = {
            "spend": self.spend,
            "immediate_response": self.immediate_response,
            "cumulative_response": self.cumulative_response,
        }
        for name, value in scalar_values.items():
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")

        sequence_values = {
            "period_responses": self.period_responses,
            "carryover_responses": self.carryover_responses,
            "adstock_decay_weights": self.adstock_decay_weights,
        }
        for name, values in sequence_values.items():
            if any(not math.isfinite(value) for value in values):
                raise ValueError(f"{name} cannot contain non-finite values")

        if any(x < 0 for x in self.period_responses):
            raise ValueError("period_responses cannot contain negative values")
        if self.immediate_response < 0:
            raise ValueError("immediate_response cannot be negative")
        if any(x < 0 for x in self.carryover_responses):
            raise ValueError("carryover_responses cannot contain negative values")
        if any(w < 0 for w in self.adstock_decay_weights):
            raise ValueError("adstock_decay_weights cannot contain negative values")
        if self.adstock_decay_weights and sum(self.adstock_decay_weights) <= 0:
            raise ValueError("adstock_decay_weights must sum to > 0 when provided")

        has_period = bool(self.period_responses)
        has_immediate_or_carry = (self.immediate_response > 0.0) or bool(self.carryover_responses)

        if not has_period and not has_immediate_or_carry and self.cumulative_response > 0:
            raise ValueError(
                "cumulative_response cannot be positive without a period response decomposition"
            )

        if has_period and has_immediate_or_carry:
            if abs(self.period_responses[0] - self.immediate_response) > 1e-4:
                raise ValueError(
                    f"Conflicting immediate response: period_responses[0]={self.period_responses[0]} "
                    f"does not match immediate_response={self.immediate_response}"
                )
            if self.carryover_responses:
                if len(self.carryover_responses) != len(self.period_responses) - 1:
                    raise ValueError(
                        f"Carryover responses length {len(self.carryover_responses)} does not match "
                        f"period_responses carryover length {len(self.period_responses) - 1}"
                    )
                for idx, (p_val, c_val) in enumerate(
                    zip(self.period_responses[1:], self.carryover_responses)
                ):
                    if abs(p_val - c_val) > 1e-4:
                        raise ValueError(
                            f"Conflicting carryover response at lag {idx + 1}: {p_val} vs {c_val}"
                        )
            else:
                self.carryover_responses = [float(x) for x in self.period_responses[1:]]
            self.cumulative_response = float(sum(self.period_responses))
        elif has_period and not has_immediate_or_carry:
            self.immediate_response = float(self.period_responses[0])
            self.carryover_responses = [float(x) for x in self.period_responses[1:]]
            self.cumulative_response = float(sum(self.period_responses))
        elif not has_period and has_immediate_or_carry:
            self.period_responses = [self.immediate_response, *self.carryover_responses]
            self.cumulative_response = float(sum(self.period_responses))
        elif has_period:
            self.cumulative_response = float(sum(self.period_responses))
        return self

    def evaluate_financials(
        self,
        revenue_per_outcome: float = 1.0,
        margin_rate: float = 1.0,
        discount_rate: float = 0.0,
    ) -> dict[str, float]:
        """Compute financial valuation of this media cohort."""
        gross_revenue = round(self.cumulative_response * revenue_per_outcome, 2)
        net_profit = round(gross_revenue * margin_rate - self.spend, 2)
        roas = round(gross_revenue / self.spend, 4) if self.spend > 0 else 0.0

        npv = (
            sum(
                (resp * revenue_per_outcome * margin_rate) / ((1.0 + discount_rate) ** idx)
                for idx, resp in enumerate(self.period_responses)
            )
            - self.spend
        )

        valuation = {
            "gross_revenue": gross_revenue,
            "net_profit": net_profit,
            "roas": roas,
            "discounted_npv": round(npv, 2),
        }
        self.financial_valuation = valuation
        return valuation


class MediaResponseCohortLedger(BaseModel):
    """Tenant-scoped ledger of media source-period response cohorts (RFC 003)."""

    ledger_id: str = Field(description="Unique media cohort ledger ID")
    tenant_id: str = Field(default="default", description="Tenant/organization identifier")
    project_id: str | None = Field(default=None, description="Optional project identifier")
    model_id: str | None = Field(default=None, description="Fitted MMM model ID")
    target_metric: str = Field(default="response", description="Target metric name")
    period_type: PeriodType = Field(default="weekly", description="Temporal granularity")
    cohorts: list[MediaResponseCohortRecord] = Field(
        default_factory=list, description="Collection of media response cohorts"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    def total_spend(self) -> float:
        """Total spend deployed across all media cohorts."""
        return sum(c.spend for c in self.cohorts)

    def total_response(self) -> float:
        """Total lifetime response across all media cohorts."""
        return sum(c.cumulative_response for c in self.cohorts)

    def total_immediate_response(self) -> float:
        """Total immediate response (lag 0) across all media cohorts."""
        return sum(c.immediate_response for c in self.cohorts)

    def total_carryover_response(self) -> float:
        """Total carryover response (lag >= 1) across all media cohorts."""
        return sum(sum(c.carryover_responses) for c in self.cohorts)

    def reconcile_to_calendar_response(
        self,
        calendar_responses: dict[str, float],
        tolerance: float = 0.05,
        period_order: list[str] | None = None,
    ) -> dict[str, Any]:
        """Reconcile source-period carryovers against authoritative calendar-period response.

        For each calendar evaluation period T, sums contributions from all source cohorts
        t where t + lag == T. Enforces period-by-period comparison to detect timing shifts.

        Authoritative media-response values are domain-constrained to finite, non-negative
        quantities. Invalid signed/non-finite inputs are rejected before discrepancy
        arithmetic so reconciliation cannot certify impossible response series.
        """
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError("tolerance must be a finite non-negative number")
        if not calendar_responses:
            raise ValueError(
                "calendar_responses must contain at least one authoritative period"
            )

        normalized_calendar: dict[str, float] = {}
        for period, raw_value in calendar_responses.items():
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"calendar response for period '{period}' must be numeric"
                ) from exc
            if not math.isfinite(value):
                raise ValueError(
                    f"calendar response for period '{period}' must be finite, got {raw_value!r}"
                )
            if value < 0:
                raise ValueError(
                    f"calendar response for period '{period}' must be non-negative, got {value}"
                )
            normalized_calendar[period] = value

        calendar_responses = normalized_calendar

        if period_order is None:
            all_periods = set(calendar_responses.keys())
            for c in self.cohorts:
                all_periods.add(c.source_period)
            period_order = sorted(
                all_periods,
                key=lambda period: _period_ordinal(period, self.period_type),
            )
        elif not period_order:
            raise ValueError("period_order cannot be empty when provided")

        if len(set(period_order)) != len(period_order):
            raise ValueError("period_order cannot contain duplicate periods")

        period_ordinals = [
            _period_ordinal(period, self.period_type) for period in period_order
        ]
        for previous, current in zip(period_ordinals, period_ordinals[1:]):
            if current != previous + 1:
                raise ValueError(
                    f"period_order must be chronological and contiguous for {self.period_type} periods"
                )

        missing_authoritative_periods = [
            period for period in calendar_responses if period not in period_order
        ]
        if missing_authoritative_periods:
            raise ValueError(
                "period_order is missing authoritative period(s): "
                + ", ".join(missing_authoritative_periods)
            )

        period_idx = {p: i for i, p in enumerate(period_order)}
        calendar_cohort_totals: dict[str, float] = {p: 0.0 for p in period_order}
        unmapped_response_total = 0.0
        unmapped_cohort_ids: set[str] = set()

        for cohort in self.cohorts:
            if cohort.source_period not in period_idx:
                unmapped_response_total += cohort.cumulative_response
                if cohort.cumulative_response > 0:
                    unmapped_cohort_ids.add(cohort.cohort_id)
                continue

            src_i = period_idx[cohort.source_period]
            for lag, response in enumerate(cohort.period_responses):
                cal_i = src_i + lag
                if cal_i >= len(period_order):
                    unmapped_response_total += response
                    if response > 0:
                        unmapped_cohort_ids.add(cohort.cohort_id)
                    continue

                calendar_period = period_order[cal_i]
                calendar_cohort_totals[calendar_period] += response

        uncovered_periods = [
            period
            for period, value in calendar_cohort_totals.items()
            if period not in calendar_responses and value > 0
        ]
        uncovered_response_total = sum(
            calendar_cohort_totals[period] for period in uncovered_periods
        )
        unmapped_response_total += uncovered_response_total

        total_cohort_sum = sum(calendar_cohort_totals.get(p, 0.0) for p in calendar_responses)
        total_authoritative_sum = sum(calendar_responses.values()) if calendar_responses else 0.0

        diff = abs(total_cohort_sum - total_authoritative_sum)
        rel_diff = (
            diff / max(1e-6, total_authoritative_sum)
            if total_authoritative_sum > 0
            else (0.0 if diff == 0.0 else 1.0)
        )
        grand_reconciled = (
            (diff == 0.0) if total_authoritative_sum == 0.0 else (rel_diff <= tolerance)
        )

        discrepant_periods: list[str] = []
        period_details: dict[str, dict[str, float | bool]] = {}

        for p, auth_val in calendar_responses.items():
            cohort_val = calendar_cohort_totals.get(p, 0.0)
            p_diff = abs(cohort_val - auth_val)
            if auth_val == 0.0:
                p_rel = 0.0 if p_diff == 0.0 else 1.0
                p_ok = (p_diff == 0.0)
            else:
                p_rel = p_diff / auth_val
                p_ok = (p_rel <= tolerance)

            period_details[p] = {
                "cohort_val": round(cohort_val, 2),
                "authoritative_val": round(auth_val, 2),
                "absolute_diff": round(p_diff, 2),
                "relative_diff_pct": round(p_rel * 100, 2),
                "is_reconciled": p_ok,
            }
            if not p_ok:
                discrepant_periods.append(p)

        is_reconciled = (
            grand_reconciled
            and len(discrepant_periods) == 0
            and unmapped_response_total == 0.0
        )

        return {
            "total_cohort_calendar_sum": round(total_cohort_sum, 2),
            "total_authoritative_sum": round(total_authoritative_sum, 2),
            "absolute_discrepancy": round(diff, 2),
            "relative_discrepancy_pct": round(rel_diff * 100, 2),
            "is_reconciled": is_reconciled,
            "discrepant_periods": discrepant_periods,
            "period_details": period_details,
            "unmapped_response_total": round(unmapped_response_total, 2),
            "unmapped_cohort_ids": sorted(unmapped_cohort_ids),
            "uncovered_periods": uncovered_periods,
            "cohort_count": len(self.cohorts),
            "calendar_periods_evaluated": len(calendar_responses),
        }
