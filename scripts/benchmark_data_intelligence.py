"""Benchmark script measuring Marketing Data Intelligence Engine throughput on representative dataset sizes."""

from __future__ import annotations

import time
import numpy as np
import pandas as pd
from marketing_mcp.intelligence.engine import MarketingDataIntelligenceEngine


def generate_synthetic_benchmark_df(n_rows: int) -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=n_rows, freq="h")
    data = {
        "date": dates,
        "revenue_usd": np.random.uniform(1000, 10000, size=n_rows),
        "meta_spend": np.random.uniform(50, 500, size=n_rows),
        "google_spend": np.random.uniform(100, 800, size=n_rows),
        "tiktok_spend": np.random.uniform(20, 300, size=n_rows),
        "youtube_spend": np.random.uniform(40, 400, size=n_rows),
        "discount_rate": np.random.uniform(0, 0.3, size=n_rows),
        "region": np.random.choice(["US_East", "US_West", "EMEA", "APAC"], size=n_rows),
    }
    return pd.DataFrame(data)


def run_benchmark():
    engine = MarketingDataIntelligenceEngine()
    print("===========================================================")
    print("   Marketing Data Intelligence Engine Performance Benchmark")
    print("===========================================================")
    sizes = [10_000, 100_000, 500_000]

    for n in sizes:
        df = generate_synthetic_benchmark_df(n)
        mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)

        t0 = time.perf_counter()
        contract = engine.analyze_dataset(df, dataset_id=f"bench_{n}")
        elapsed = time.perf_counter() - t0

        rows_per_sec = n / max(1e-6, elapsed)
        print(f"Rows: {n:>7,d} | Mem: {mem_mb:>6.1f} MB | Time: {elapsed:>6.3f}s | Throughput: {rows_per_sec:>10,.0f} rows/s | Target: {contract.target.column} | Channels: {len(contract.channels)}")


if __name__ == "__main__":
    run_benchmark()
