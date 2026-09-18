"""Response Cohort Ledger builder and analysis service (T7)."""

from __future__ import annotations

import uuid
from typing import Any

import pandas as pd

from marketing_mcp.domain.cohorts.contracts import (
    CohortRecord,
    PeriodType,
    ResponseCohortLedger,
)


def build_cohort_ledger(
    cohort_data: list[dict[str, Any]],
    ledger_id: str | None = None,
    tenant_id: str = "default",
    project_id: str | None = None,
    target_metric: str = "revenue",
    period_type: PeriodType = "weekly",
) -> ResponseCohortLedger:
    """Construct a ResponseCohortLedger from cohort aggregation records.

    Each entry in cohort_data should specify:
    - acquisition_period (str)
    - period_revenues (list[float])
    - acquired_customers (optional int)
    - channel (optional str)
    """
    lid = ledger_id or f"ledger_{uuid.uuid4().hex[:10]}"
    cohort_records: list[CohortRecord] = []

    for item in cohort_data:
        acq = item["acquisition_period"]
        p_revs = [float(r) for r in item.get("period_revenues", [])]
        cum_rev = float(sum(p_revs))

        # Compute empirical maturity curve
        maturity: list[float] = []
        if cum_rev > 0:
            running = 0.0
            for r in p_revs:
                running += r
                maturity.append(round(running / cum_rev, 4))
        else:
            maturity = [1.0] * len(p_revs)

        # Lag periods until 95% mature
        lag_95 = len(p_revs)
        for idx, frac in enumerate(maturity):
            if frac >= 0.95:
                lag_95 = idx
                break

        rec = CohortRecord(
            cohort_id=f"cohort_{acq}",
            acquisition_period=acq,
            channel=item.get("channel"),
            acquired_customers=item.get("acquired_customers"),
            period_revenues=p_revs,
            cumulative_revenue=round(cum_rev, 2),
            maturity_curve=maturity,
            observational_lag_periods=lag_95,
            provenance={"source": item.get("source", "user_cohort_input")},
        )
        cohort_records.append(rec)

    return ResponseCohortLedger(
        ledger_id=lid,
        tenant_id=tenant_id,
        project_id=project_id,
        target_metric=target_metric,
        period_type=period_type,
        cohorts=cohort_records,
    )


def extract_cohorts_from_transactions(
    df: pd.DataFrame,
    customer_id_col: str,
    date_col: str,
    value_col: str,
    freq: str = "W-MON",
    tenant_id: str = "default",
) -> ResponseCohortLedger:
    """Build a ResponseCohortLedger from raw transaction timestamps and customer IDs.

    Computes true cohort boundaries from first transaction timestamp.
    Never fakes or imputes unobserved customer-level microdata.
    """
    df_clean = df[[customer_id_col, date_col, value_col]].copy()
    df_clean[date_col] = pd.to_datetime(df_clean[date_col])
    df_clean[value_col] = pd.to_numeric(df_clean[value_col], errors="coerce").fillna(0.0)

    # First transaction per customer defines acquisition period
    first_tx = df_clean.groupby(customer_id_col)[date_col].min().reset_index()
    first_tx["cohort_period"] = first_tx[date_col].dt.to_period(freq).astype(str)

    merged = df_clean.merge(first_tx[[customer_id_col, "cohort_period"]], on=customer_id_col)
    merged["tx_period"] = merged[date_col].dt.to_period(freq).astype(str)

    cohorts_data = []
    unique_cohorts = sorted(merged["cohort_period"].unique())

    for c_p in unique_cohorts:
        c_df = merged[merged["cohort_period"] == c_p]
        n_cust = c_df[customer_id_col].nunique()

        # Group by period offset
        all_tx_periods = sorted(c_df["tx_period"].unique())
        p_revs = []
        for p in all_tx_periods:
            rev = float(c_df[c_df["tx_period"] == p][value_col].sum())
            p_revs.append(round(rev, 2))

        cohorts_data.append({
            "acquisition_period": c_p,
            "acquired_customers": n_cust,
            "period_revenues": p_revs,
        })

    return build_cohort_ledger(cohorts_data, tenant_id=tenant_id)
