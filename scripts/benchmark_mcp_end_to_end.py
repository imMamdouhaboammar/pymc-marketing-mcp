"""Benchmark the real Streamable HTTP MCP request path with Rust enabled and disabled across 7 scenarios."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pandas as pd


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def _summary(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": round(statistics.fmean(samples), 4),
        "p50_ms": round(_percentile(samples, 0.50), 4),
        "p95_ms": round(_percentile(samples, 0.95), 4),
        "p99_ms": round(_percentile(samples, 0.99), 4),
    }


async def _worker(iterations: int, warmup: int) -> dict[str, Any]:
    import httpx2
    import uvicorn
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from marketing_mcp.accelerators import (
        compress_curve_lttb,
        get_engine_info,
        get_native_invocation_stats,
    )
    from marketing_mcp.app import Application
    from marketing_mcp.cli import create_http_app
    from marketing_mcp.config import Settings

    with tempfile.TemporaryDirectory(prefix="mcp-e2e-bench-") as directory:
        root = Path(directory)
        settings = Settings(
            data_dir=root / "data",
            artifact_dir=root / "artifacts",
            metadata_db=root / "metadata.db",
            ingest_dir=root,
            auth_enabled=False,
            job_execution_mode="enqueue-only",
            rate_limit_per_minute=100000,
        )
        app_instance = Application(settings)

        # 1. Preload a valid MMM dataset (60 weekly records) for inspection & job submission
        dates = pd.date_range("2022-01-01", periods=60, freq="W-MON").strftime("%Y-%m-%d").tolist()
        csv_rows = ["date,revenue,facebook,google"]
        for i, d in enumerate(dates):
            csv_rows.append(f"{d},{1000 + i * 10},{100 + (i % 7) * 15},{200 + (i % 5) * 20}")
        csv_data = "\n".join(csv_rows)
        dataset_reg = app_instance.datasets.register_bytes(
            csv_data.encode("utf-8"),
            format="csv",
            filename="benchmark_mmm.csv",
        )
        dataset_id = dataset_reg.dataset_id

        # 2. Preload an artifact for Range header download benchmark
        artifact_raw = b"PYMC_MARKETING_BENCHMARK_ARTIFACT_PAYLOAD_CHUNK_DATA_" * 1000
        owner = "benchmark"
        tenant_id = "default"
        art_ref = app_instance.artifacts.put_bytes(
            artifact_raw,
            content_type="application/octet-stream",
            owner=owner,
            tenant_id=tenant_id,
        )
        art_namespace = app_instance.artifacts._namespace(owner, tenant_id)
        art_sha = art_ref.sha256

        # 3. Build ASGI application and spin up Uvicorn server
        app = create_http_app(application=app_instance, settings=settings)
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]

        scenario_results: dict[str, Any] = {}
        cpu_start = time.process_time()
        wall_start = time.perf_counter()

        try:
            async with (
                httpx2.AsyncClient() as http_client,
                streamable_http_client(f"http://127.0.0.1:{port}/mcp", http_client=http_client) as (
                    read_stream,
                    write_stream,
                ),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()

                # Scenario 1: MCP Discovery (tools/list)
                disc_samples: list[float] = []
                for _ in range(warmup):
                    await session.list_tools()
                for _ in range(iterations):
                    t0 = time.perf_counter_ns()
                    tools_list = await session.list_tools()
                    disc_samples.append((time.perf_counter_ns() - t0) / 1_000_000)
                if not tools_list.tools:
                    raise RuntimeError("MCP discovery returned no tools")
                scenario_results["mcp_discovery"] = {
                    "latency": _summary(disc_samples),
                    "throughput_requests_per_second": round(iterations / (sum(disc_samples) / 1000), 2),
                    "tool_count": len(tools_list.tools),
                }

                # Scenario 2: Tiny Tool (get_model_status)
                tiny_samples: list[float] = []
                for _ in range(warmup):
                    await session.call_tool("get_model_status", arguments={"model_id": "missing-model"})
                for _ in range(iterations):
                    t0 = time.perf_counter_ns()
                    res = await session.call_tool("get_model_status", arguments={"model_id": "missing-model"})
                    tiny_samples.append((time.perf_counter_ns() - t0) / 1_000_000)
                if not res.content:
                    raise RuntimeError("Tiny tool returned no content")
                scenario_results["tiny_tool"] = {
                    "latency": _summary(tiny_samples),
                    "throughput_requests_per_second": round(iterations / (sum(tiny_samples) / 1000), 2),
                }

                # Scenario 3: Dataset Inspection (inspect_dataset)
                ds_samples: list[float] = []
                for _ in range(warmup):
                    await session.call_tool("inspect_dataset", arguments={"dataset_id": dataset_id})
                for _ in range(iterations):
                    t0 = time.perf_counter_ns()
                    res = await session.call_tool("inspect_dataset", arguments={"dataset_id": dataset_id})
                    ds_samples.append((time.perf_counter_ns() - t0) / 1_000_000)
                if not res.content:
                    raise RuntimeError("Dataset inspect returned no content")
                scenario_results["dataset_inspection"] = {
                    "latency": _summary(ds_samples),
                    "throughput_requests_per_second": round(iterations / (sum(ds_samples) / 1000), 2),
                }

                # Scenario 4: Job Submission (submit_fit_mmm_job admission latency)
                job_sub_samples: list[float] = []
                fit_config = {
                    "dataset_id": dataset_id,
                    "date_column": "date",
                    "target_column": "revenue",
                    "channel_columns": ["facebook", "google"],
                    "model_type": "mmm",
                }
                for _ in range(warmup):
                    await session.call_tool("submit_fit_mmm_job", arguments={"config": fit_config})
                for _ in range(iterations):
                    t0 = time.perf_counter_ns()
                    res = await session.call_tool("submit_fit_mmm_job", arguments={"config": fit_config})
                    job_sub_samples.append((time.perf_counter_ns() - t0) / 1_000_000)
                if not res.content:
                    raise RuntimeError("Job submission returned no content")
                scenario_results["job_submission"] = {
                    "latency": _summary(job_sub_samples),
                    "throughput_requests_per_second": round(iterations / (sum(job_sub_samples) / 1000), 2),
                }

                # Scenario 5: Job Polling (list_jobs)
                poll_samples: list[float] = []
                for _ in range(warmup):
                    await session.call_tool("list_jobs", arguments={"limit": 20})
                for _ in range(iterations):
                    t0 = time.perf_counter_ns()
                    res = await session.call_tool("list_jobs", arguments={"limit": 20})
                    poll_samples.append((time.perf_counter_ns() - t0) / 1_000_000)
                if not res.content:
                    raise RuntimeError("Job polling returned no content")
                scenario_results["job_polling"] = {
                    "latency": _summary(poll_samples),
                    "throughput_requests_per_second": round(iterations / (sum(poll_samples) / 1000), 2),
                }

                # Scenario 6: Response Curves LTTB (5,000 points downsampled to 30)
                xs = [float(i) for i in range(5000)]
                ys = [math.sin(i / 100.0) + math.log(i + 1) for i in range(5000)]
                lttb_samples: list[float] = []
                for _ in range(warmup):
                    compress_curve_lttb(xs, ys, max_points=30)
                for _ in range(iterations):
                    t0 = time.perf_counter_ns()
                    compress_curve_lttb(xs, ys, max_points=30)
                    lttb_samples.append((time.perf_counter_ns() - t0) / 1_000_000)
                scenario_results["curves_lttb"] = {
                    "latency": _summary(lttb_samples),
                    "throughput_requests_per_second": round(iterations / (sum(lttb_samples) / 1000), 2),
                    "source_points": 5000,
                    "target_points": 30,
                }

                # Scenario 7: Artifact Delivery (GET /artifacts/... with Range header)
                artifact_url = f"http://127.0.0.1:{port}/artifacts/{art_namespace}/{art_sha}/download"
                range_headers = {"Range": "bytes=100-2000"}
                art_samples: list[float] = []
                for _ in range(warmup):
                    resp = await http_client.get(artifact_url, headers=range_headers)
                    if resp.status_code != 206:
                        raise RuntimeError(f"Artifact Range download failed with status {resp.status_code}")
                for _ in range(iterations):
                    t0 = time.perf_counter_ns()
                    resp = await http_client.get(artifact_url, headers=range_headers)
                    _ = resp.content
                    art_samples.append((time.perf_counter_ns() - t0) / 1_000_000)
                    if resp.status_code != 206:
                        raise RuntimeError(f"Artifact Range download failed with status {resp.status_code}")
                scenario_results["artifact_delivery"] = {
                    "latency": _summary(art_samples),
                    "throughput_requests_per_second": round(iterations / (sum(art_samples) / 1000), 2),
                    "requested_range": "bytes=100-2000",
                }

        finally:
            server.should_exit = True
            await server_task

        wall_seconds = time.perf_counter() - wall_start
        cpu_seconds = time.process_time() - cpu_start
        max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        max_rss_mib = round(max_rss / (1024 * 1024 if sys.platform == "darwin" else 1024), 2)

        return {
            "engine": get_engine_info(),
            "iterations": iterations,
            "warmup": warmup,
            "scenarios": scenario_results,
            "wall_seconds": round(wall_seconds, 4),
            "cpu_seconds": round(cpu_seconds, 4),
            "max_rss_mib": max_rss_mib,
            "native_counters": get_native_invocation_stats(),
        }


def _run_backend(backend: str, iterations: int, warmup: int) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["MARKETING_MCP_DISABLE_RUST"] = "1" if backend == "python" else "0"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--iterations",
        str(iterations),
        "--warmup",
        str(warmup),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(completed.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Scenario End-to-End MCP Benchmark")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.iterations < 1 or args.warmup < 0:
        parser.error("iterations must be positive and warmup must be non-negative")

    if args.worker:
        print(json.dumps(asyncio.run(_worker(args.iterations, args.warmup))))
        return

    python_data = _run_backend("python", args.iterations, args.warmup)
    rust_data = _run_backend("rust", args.iterations, args.warmup)

    scenarios = list(python_data.get("scenarios", {}).keys())
    comparison: dict[str, Any] = {}
    for s in scenarios:
        py_lat = python_data["scenarios"][s]["latency"]
        ru_lat = rust_data["scenarios"][s]["latency"]
        speedup_mean = round(py_lat["mean_ms"] / ru_lat["mean_ms"], 2) if ru_lat["mean_ms"] > 0 else 1.0
        speedup_p95 = round(py_lat["p95_ms"] / ru_lat["p95_ms"], 2) if ru_lat["p95_ms"] > 0 else 1.0
        comparison[s] = {
            "python_mean_ms": py_lat["mean_ms"],
            "rust_mean_ms": ru_lat["mean_ms"],
            "speedup_mean": speedup_mean,
            "python_p95_ms": py_lat["p95_ms"],
            "rust_p95_ms": ru_lat["p95_ms"],
            "speedup_p95": speedup_p95,
        }

    report = {
        "scope": "real local HTTP/SSE MCP transport across 7 operational scenarios",
        "units": {"latency": "milliseconds", "memory": "MiB"},
        "backends": {
            "python": python_data,
            "rust": rust_data,
        },
        "comparison": comparison,
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

