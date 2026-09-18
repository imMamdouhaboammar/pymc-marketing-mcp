"""Single-pass structural profiler for tabular marketing data."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.profile import (
    CategoricalDistribution,
    ColumnProfile,
    StructuralProfile,
)

from .dates import detect_temporal_profile
from .missingness import profile_missingness
from .numeric import profile_numeric


def profile_structure(df: pd.DataFrame, date_column: str | None = None) -> StructuralProfile:
    """Runs single-pass structural profiling on the dataset."""
    rows = len(df)
    cols = len(df.columns)
    memory_bytes = int(df.memory_usage(deep=True).sum())
    dup_rows = int(df.duplicated().sum())

    temporal = detect_temporal_profile(df, date_column=date_column)
    column_profiles: dict[str, ColumnProfile] = {}

    for col in df.columns:
        s = df[col]
        missing = profile_missingness(s)
        is_num = pd.api.types.is_numeric_dtype(s)
        is_dt = pd.api.types.is_datetime64_any_dtype(s) or (col == temporal.date_column)

        num_dist = profile_numeric(s) if is_num else None
        cat_dist = None

        if not is_num and not is_dt:
            unique_vals = s.dropna().value_counts()
            cardinality = len(unique_vals)
            top_vals = [(str(k), int(v)) for k, v in unique_vals.head(5).items()]
            # rare values: frequency < 1%
            rare_threshold = max(1, int(rows * 0.01))
            rare_count = int((unique_vals < rare_threshold).sum())
            cat_dist = CategoricalDistribution(
                cardinality=cardinality,
                top_values=top_vals,
                rare_values_count=rare_count,
            )
            inferred_type = "categorical" if cardinality < rows * 0.5 else "textual"
        elif is_dt:
            inferred_type = "datetime"
        elif pd.api.types.is_integer_dtype(s):
            inferred_type = "integer"
        else:
            inferred_type = "float"

        column_profiles[col] = ColumnProfile(
            name=col,
            physical_dtype=str(s.dtype),
            inferred_type=inferred_type,
            row_count=rows,
            missingness=missing,
            numeric=num_dist,
            categorical=cat_dist,
        )

    return StructuralProfile(
        rows=rows,
        columns=cols,
        memory_bytes=memory_bytes,
        duplicate_rows=dup_rows,
        temporal=temporal,
        column_profiles=column_profiles,
    )
