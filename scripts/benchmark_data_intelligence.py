"""Benchmark script measuring empirical performance of Marketing Data Intelligence Engine."""

from __future__ import annotations

import time
import numpy as np
import pandas as pd

from marketing_mcp.intelligence.engine import MarketingDataIntelligenceEngine
from marketing_mcp.intelligence.structural.profiler import profile_structure
from marketing_mcp.intelligence.semantics.roles import infer_all_column_roles


def generate_benchmark_dataset(rows: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-01", periods=rows, freq="h")
    return pd.DataFrame({
        "date": dates,
        "revenue_usd": rng.normal(50000, 5000, size=rows).clip(0),
        "meta_spend": rng.exponential(1500, size=rows),
        "google_spend": rng.exponential(2000, size=rows),
        "tiktok_spend": rng.exponential(800, size=rows),
        "youtube_spend": rng.exponential(1200, size=rows),
        "discount_rate": rng.uniform(0.0, 0.3, size=rows),
        "market": rng.choice(["US", "UK", "DE", "FR"], size=rows),
        "campaign_objective": rng.choice(["Sales", "Awareness", "Traffic"], size=rows),
        "platform_attributed_revenue": rng.normal(20000, 3000, size=rows).clip(0),
    })


def run_benchmark(sizes: list[int] = [10_000, 100_000]) -> list[dict]:
    engine = MarketingDataIntelligenceEngine()
    results = []

    print(f"=== Marketing Data Intelligence Engine Performance Benchmark ===")
    for rows in sizes:
        print(f"\n[Benchmarking {rows:,} rows x 10 columns]...")
        t0 = time.perf_counter()
        df = generate_benchmark_dataset(rows)
        gen_time = time.perf_counter() - t0

        mem_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)

        # 1. Structural profiling alone
        t_struct_start = time.perf_counter()
        structural = profile_structure(df)
        t_struct = time.perf_counter() - t_struct_start

        # 2. Semantic inference alone
        t_sem_start = time.perf_counter()
        roles = infer_all_column_roles(df, structural)
        t_sem = time.perf_counter() - t_sem_start

        # 3. Full end-to-end intelligence engine
        t_e2e_start = time.perf_counter()
        contract = engine.analyze_dataset(df, dataset_id=f"bench_{rows}")
        t_e2e = time.perf_counter() - t_e2e_start

        throughput = rows / t_e2e

        res = {
            "rows": rows,
            "columns": len(df.columns),
            "memory_mb": round(mem_mb, 2),
            "structural_profiling_s": round(t_struct, 4),
            "semantic_inference_s": round(t_sem, 4),
            "full_engine_e2e_s": round(t_e2e, 4),
            "throughput_rows_per_s": round(throughput, 1),
            "issues_count": len(contract.issues),
            "suitability": contract.suitability[list(contract.suitability.keys())[0]].verdict.value,
        }
        results.append(res)
        print(f"  Memory: {res['memory_mb']} MB")
        print(f"  Structural Profiling: {res['structural_profiling_s']} s")
        print(f"  Semantic Inference:   {res['semantic_inference_s']} s")
        print(f"  End-to-End Analysis:  {res['full_engine_e2e_s']} s")
        print(f"  Throughput:           {res['throughput_rows_per_s']:,} rows/sec")

    return results


if __name__ == "__main__":
    results = run_benchmark([10_000, 100_000])
    print("\n| Rows | Columns | Memory (MB) | Structural (s) | Semantics (s) | E2E Total (s) | Throughput (rows/s) |")
    print("|------|---------|-------------|----------------|---------------|---------------|---------------------|")
    for r in results:
        print(f"| {r['rows']:,} | {r['columns']} | {r['memory_mb']} | {r['structural_profiling_s']} | {r['semantic_inference_s']} | {r['full_engine_e2e_s']} | {r['throughput_rows_per_s']:,} |")
