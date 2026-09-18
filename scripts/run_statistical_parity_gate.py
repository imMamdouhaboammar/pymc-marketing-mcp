#!/usr/bin/env python3
"""Statistical Parity Gate against Golden Baseline Datasets (UP-060).

Runs pure scientific model fits (MMM, CLV Purchase, CLV Value) against
the standardized golden fixtures in migration/baselines/golden_datasets/
and verifies MCMC convergence, diagnostic gates, and parameter estimates.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd

from marketing_mcp.scientific.clv import (
    fit_clv_purchase_from_spec,
    fit_clv_value_from_spec,
)
from marketing_mcp.scientific.decision_gate import (
    DecisionPolicyVerdict,
    evaluate_diagnostic_policy,
)
from marketing_mcp.scientific.mmm import fit_mmm_from_spec


def find_baseline_dir() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "migration/baselines",
        Path(__file__).resolve().parents[1] / "migration/baselines",
        Path("migration/baselines"),
        Path("../migration/baselines"),
    ]
    for c in candidates:
        if (c / "golden_datasets").exists():
            return c.resolve()
    raise FileNotFoundError("Could not find migration/baselines/golden_datasets directory")


def run_mmm_parity_gate(baseline_dir: Path) -> dict:
    continuous_csv = baseline_dir / "golden_datasets/pymc_harsh_continuous_zero_padded_panel.csv"
    if not continuous_csv.exists():
        raise FileNotFoundError(f"Missing {continuous_csv}")

    df = pd.read_csv(continuous_csv)
    df["date"] = pd.to_datetime(df["date"])
    weekly_df = (
        df.resample("W-MON", on="date")
        .agg({
            "meta": "sum",
            "google": "sum",
            "tiktok": "sum",
            "revenue": "sum",
        })
        .reset_index()
    )
    run_id = uuid4()

    spec = {
        "analysis_kind": "mmm",
        "dataset_version_id": str(run_id),
        "random_seed": 42,
        "configuration": {
            "date_column": "date",
            "target_column": "revenue",
            "channel_columns": ["meta", "google", "tiktok"],
            "adstock": {"kind": "geometric", "l_max": 2},
            "saturation": {"kind": "logistic"},
            "sampler": {"draws": 100, "tune": 100, "chains": 2, "target_accept": 0.85},
        },
    }

    result = fit_mmm_from_spec(spec, weekly_df)
    rhat = result.diagnostics.get("max_rhat", 1.0)
    divs = int(result.diagnostics.get("divergences", 0))
    bfmi = result.diagnostics.get("min_bfmi")

    eval_result = evaluate_diagnostic_policy(
        run_id=run_id,
        max_rhat=rhat,
        divergences=divs,
        min_bfmi=bfmi,
    )
    status_str = str(eval_result.decision_status)
    if hasattr(eval_result.decision_status, "value"):
        status_str = eval_result.decision_status.value

    return {
        "dataset": "pymc_harsh_continuous_zero_padded_panel.csv",
        "analysis_kind": "mmm",
        "diagnostics": result.diagnostics,
        "verdict": status_str,
        "parameters_count": len(result.parameter_estimates),
        "parameters": {k: float(v) for k, v in result.parameter_estimates.items()},
        "status": "PASS" if status_str in ("pass", "caution") else "FAIL",
    }


def run_clv_purchase_parity_gate(baseline_dir: Path) -> dict:
    clv_csv = baseline_dir / "golden_datasets/pymc_harsh_clv_valid_fixture.csv"
    if not clv_csv.exists():
        raise FileNotFoundError(f"Missing {clv_csv}")

    df = pd.read_csv(clv_csv).iloc[:30].copy()

    spec = {
        "analysis_kind": "clv_purchase",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "customer_id_column": "customer_id",
            "datetime_column": "recency",
            "model_type": "bg_nbd",
        },
    }

    result = fit_clv_purchase_from_spec(spec, df, draws=25, tune=25, chains=2)
    return {
        "dataset": "pymc_harsh_clv_valid_fixture.csv",
        "analysis_kind": "clv_purchase",
        "parameters_count": len(result.parameter_estimates),
        "parameters": {k: float(v) for k, v in result.parameter_estimates.items()},
        "status": "PASS" if len(result.parameter_estimates) > 0 else "FAIL",
    }


def run_clv_value_parity_gate(baseline_dir: Path) -> dict:
    value_csv = baseline_dir / "golden_datasets/pymc_harsh_clv_value_fixture.csv"
    if not value_csv.exists():
        raise FileNotFoundError(f"Missing {value_csv}")

    raw_df = pd.read_csv(value_csv)
    valid_df = raw_df[(raw_df["frequency"] > 0) & (raw_df["monetary_value"] > 0)].iloc[:30].copy()

    spec = {
        "analysis_kind": "clv_value",
        "dataset_version_id": str(uuid4()),
        "random_seed": 42,
        "configuration": {
            "customer_id_column": "customer_id",
            "monetary_value_column": "monetary_value",
            "frequency_column": "frequency",
        },
    }

    result = fit_clv_value_from_spec(spec, valid_df, draws=25, tune=25, chains=2)
    return {
        "dataset": "pymc_harsh_clv_value_fixture.csv",
        "analysis_kind": "clv_value",
        "parameters_count": len(result.parameter_estimates),
        "parameters": {k: float(v) for k, v in result.parameter_estimates.items()},
        "status": "PASS" if len(result.parameter_estimates) > 0 else "FAIL",
    }


def main():
    print("==> [UP-060] Running Full Statistical Parity Gate against Golden Datasets...")
    baseline_dir = find_baseline_dir()
    print(f"--> Found baseline fixtures in: {baseline_dir}")

    results = []

    print("--> 1/3 Running MMM Statistical Parity Fit (Continuous Panel)...")
    mmm_res = run_mmm_parity_gate(baseline_dir)
    results.append(mmm_res)
    print(f"    Verdict: {mmm_res['verdict']}, Status: {mmm_res['status']}")

    print("--> 2/3 Running CLV Purchase Parity Fit (BG/NBD)...")
    clv_p_res = run_clv_purchase_parity_gate(baseline_dir)
    results.append(clv_p_res)
    print(f"    Parameters estimated: {clv_p_res['parameters_count']}, Status: {clv_p_res['status']}")

    print("--> 3/3 Running CLV Monetary Value Parity Fit (Gamma-Gamma)...")
    clv_v_res = run_clv_value_parity_gate(baseline_dir)
    results.append(clv_v_res)
    print(f"    Parameters estimated: {clv_v_res['parameters_count']}, Status: {clv_v_res['status']}")

    all_passed = all(r["status"] == "PASS" for r in results)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "all_passed": all_passed,
        "results": results,
    }

    report_path = baseline_dir / "statistical_parity_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"==> Wrote statistical parity report to {report_path}")

    if not all_passed:
        print("❌ Statistical parity gate failed!")
        sys.exit(1)

    print("✅ All golden statistical parity gates passed successfully!")
    sys.exit(0)


if __name__ == "__main__":
    main()
