"""Response Cohort Ledger builder and analysis service (T7 & RFC 003).

Provides:
- Customer acquisition cohort building from transaction microdata or summary tables.
- Media source-period response cohort decomposition using fitted adstock weights.
"""

from __future__ import annotations

import uuid
from typing import Any

import pandas as pd

from marketing_mcp.domain.cohorts.contracts import (
    CohortRecord,
    MediaResponseCohortLedger,
    MediaResponseCohortRecord,
    PeriodType,
    ResponseCohortLedger,
)
from marketing_mcp.domain.decisions.financial import FinancialAssumptions
from marketing_mcp.errors import DomainError


def build_cohort_ledger(
    cohort_data: list[dict[str, Any]],
    ledger_id: str | None = None,
    tenant_id: str = "default",
    project_id: str | None = None,
    target_metric: str = "revenue",
    period_type: PeriodType = "weekly",
) -> ResponseCohortLedger:
    """Construct a CustomerAcquisitionCohortLedger from customer cohort records.

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

        cohorts_data.append(
            {
                "acquisition_period": c_p,
                "acquired_customers": n_cust,
                "period_revenues": p_revs,
            }
        )

    return build_cohort_ledger(cohorts_data, tenant_id=tenant_id)


def build_media_response_cohort_ledger(
    spend_records: list[dict[str, Any]],
    adstock_weights: dict[str, list[float]],
    channel_response_rates: dict[str, float] | None = None,
    financial: FinancialAssumptions | None = None,
    ledger_id: str | None = None,
    tenant_id: str = "default",
    project_id: str | None = None,
    model_id: str | None = None,
    target_metric: str = "response",
    period_type: PeriodType = "weekly",
) -> MediaResponseCohortLedger:
    """Construct a MediaResponseCohortLedger decomposing spend into carryover response cohorts (RFC 003).

    Parameters
    ----------
    spend_records:
        List of dicts with 'source_period', 'channel', 'spend', and optional 'total_response'.
    adstock_weights:
        Mapping of channel name to list of lag weights [w_0, w_1, ..., w_L] from fitted model.
    channel_response_rates:
        Optional mapping of channel to incremental response per dollar of spend.
    financial:
        Optional FinancialAssumptions for cohort valuation (gross revenue, net profit, ROAS, NPV).
    """
    if financial is not None:
        fin_errors = financial.validate()
        if fin_errors:
            raise DomainError(
                "INPUT_INVALID",
                f"Invalid financial assumptions: {'; '.join(fin_errors)}",
            )

    lid = ledger_id or f"media_ledger_{uuid.uuid4().hex[:10]}"
    cohorts: list[MediaResponseCohortRecord] = []
    seen_cohorts: set[tuple[str, str]] = set()

    for item in spend_records:
        src = str(item["source_period"])
        ch = str(item["channel"])
        key = (src, ch)
        if key in seen_cohorts:
            raise DomainError(
                "INPUT_INVALID",
                f"Duplicate spend record for period '{src}' and channel '{ch}'",
            )
        seen_cohorts.add(key)

        spend = float(item.get("spend", 0.0))
        if spend < 0:
            raise DomainError(
                "INPUT_INVALID",
                f"Spend for channel '{ch}' in period '{src}' must be non-negative, got {spend}",
            )

        if "total_response" in item:
            tot_resp = float(item["total_response"])
        elif channel_response_rates and ch in channel_response_rates:
            tot_resp = spend * float(channel_response_rates[ch])
        else:
            raise DomainError(
                "INPUT_INVALID",
                f"Missing total_response or channel_response_rate for channel '{ch}' in period '{src}'",
            )

        if tot_resp < 0:
            raise DomainError(
                "INPUT_INVALID",
                f"total_response for channel '{ch}' in period '{src}' must be non-negative, got {tot_resp}",
            )

        if ch not in adstock_weights:
            raise DomainError(
                "INPUT_INVALID",
                f"Missing adstock weights for channel '{ch}' in period '{src}'",
            )

        raw_weights = adstock_weights[ch]
        if not raw_weights or any(w < 0 for w in raw_weights) or sum(raw_weights) <= 0:
            raise DomainError(
                "INPUT_INVALID",
                f"Adstock weights for channel '{ch}' must be non-empty, non-negative, and sum to > 0, got {raw_weights}",
            )
        total_w = sum(raw_weights)
        norm_weights = [float(w) / total_w for w in raw_weights]

        immediate = round(tot_resp * norm_weights[0], 4)
        carryovers = [round(tot_resp * w, 4) for w in norm_weights[1:]]
        period_resps = [immediate, *carryovers]

        cid = f"media_{src}_{ch}"
        record = MediaResponseCohortRecord(
            cohort_id=cid,
            source_period=src,
            channel=ch,
            spend=spend,
            immediate_response=immediate,
            carryover_responses=carryovers,
            period_responses=period_resps,
            cumulative_response=round(tot_resp, 4),
            adstock_decay_weights=norm_weights,
            provenance={"source": "media_spend_adstock_decomposition"},
        )

        if financial is not None:
            record.evaluate_financials(
                revenue_per_outcome=financial.revenue_per_outcome,
                margin_rate=financial.effective_margin_rate(),
                discount_rate=financial.discount_rate,
            )

        cohorts.append(record)

    return MediaResponseCohortLedger(
        ledger_id=lid,
        tenant_id=tenant_id,
        project_id=project_id,
        model_id=model_id,
        target_metric=target_metric,
        period_type=period_type,
        cohorts=cohorts,
    )
