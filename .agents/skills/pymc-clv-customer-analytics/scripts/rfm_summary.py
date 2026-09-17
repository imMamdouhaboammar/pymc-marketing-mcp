#!/usr/bin/env python3
"""Convert raw transaction logs (customer_id, date, amount) into RFM summary dataframe for PyMC-Marketing CLV.

Outputs frequency, recency, T, and average monetary_value per repeat purchase.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def summary_data_from_transactions(
    df: pd.DataFrame,
    customer_id_col: str,
    datetime_col: str,
    monetary_value_col: str | None = None,
    observation_period_end: str | None = None,
    freq: str = "W",
) -> pd.DataFrame:
    df = df.copy()
    df[datetime_col] = pd.to_datetime(df[datetime_col])
    if observation_period_end is None:
        end_date = df[datetime_col].max()
    else:
        end_date = pd.to_datetime(observation_period_end)

    df = df[df[datetime_col] <= end_date]

    def _calc_rfm(group: pd.DataFrame) -> pd.Series:
        d = {}
        dates = group[datetime_col].sort_values()
        first_date = dates.iloc[0]
        last_date = dates.iloc[-1]

        unique_dates = dates.dt.to_period(freq).unique()
        d["frequency"] = max(0, len(unique_dates) - 1)

        if freq == "W":
            d["recency"] = (last_date - first_date).days / 7.0
            d["T"] = (end_date - first_date).days / 7.0
        elif freq == "D":
            d["recency"] = float((last_date - first_date).days)
            d["T"] = float((end_date - first_date).days)
        elif freq == "M":
            d["recency"] = (last_date - first_date).days / 30.4375
            d["T"] = (end_date - first_date).days / 30.4375

        if monetary_value_col and monetary_value_col in group.columns:
            if len(group) > 1:
                repeat_spend = group.iloc[1:][monetary_value_col].mean()
                d["monetary_value"] = repeat_spend if not np.isnan(repeat_spend) else 0.0
            else:
                d["monetary_value"] = 0.0

        return pd.Series(d)

    # Use include_groups=False for compatibility with pandas >= 2.2
    try:
        rfm = df.groupby(customer_id_col).apply(_calc_rfm, include_groups=False).reset_index()
    except TypeError:
        rfm = df.groupby(customer_id_col).apply(_calc_rfm).reset_index()

    return rfm


def main():
    parser = argparse.ArgumentParser(description="Convert transaction log to RFM summary.")
    parser.add_argument("file", help="Path to CSV or Parquet transaction log")
    parser.add_argument("--customer-id", required=True, help="Customer ID column name")
    parser.add_argument("--date", required=True, help="Date column name")
    parser.add_argument("--amount", help="Spend/Monetary amount column name")
    parser.add_argument("--freq", default="W", choices=["D", "W", "M"], help="Time frequency unit")
    parser.add_argument("--output", required=True, help="Output CSV path for RFM summary")
    args = parser.parse_args()

    p = Path(args.file)
    if p.suffix.lower() == ".parquet":
        df = pd.read_parquet(p)
    else:
        df = pd.read_csv(p)

    rfm = summary_data_from_transactions(
        df,
        customer_id_col=args.customer_id,
        datetime_col=args.date,
        monetary_value_col=args.amount,
        freq=args.freq,
    )
    rfm.to_csv(args.output, index=False)
    print(f"Successfully generated RFM summary with {len(rfm)} customers to {args.output}")


if __name__ == "__main__":
    main()
