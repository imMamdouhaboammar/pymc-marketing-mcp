"""Benchmark the real Streamable HTTP MCP request path with Rust enabled and disabled."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


def _percentile(samples: list[float], fraction: float) -> float:
    ordered = sorted(samples)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def _summary(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": statistics.fmean(samples),
        "p50_ms": _percentile(samples, 0.50),
        "p95_ms": _percentile(samples, 0.95),
        "p99_ms": _percentile(samples, 0.99),
    }


async def _worker(iterations: int, warmup: int) -> dict[str, Any]:
    import httpx2
    import uvicorn
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    from marketing_mcp.accelerators import get_engine_info, get_native_invocation_stats
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
        )
        app = create_http_app(application=Application(settings), settings=settings)
        config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]

        samples: list[float] = []
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
                for _ in range(warmup):
                    await session.call_tool(
                        "get_model_status", arguments={"model_id": "benchmark-missing"}
                    )
                for _ in range(iterations):
                    started = time.perf_counter_ns()
                    result = await session.call_tool(
                        "get_model_status", arguments={"model_id": "benchmark-missing"}
                    )
                    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
                    if not result.content:
                        raise RuntimeError("MCP tool call returned no content")
                    samples.append(elapsed_ms)
        finally:
            server.should_exit = True
            await server_task

        wall_seconds = time.perf_counter() - wall_start
        cpu_seconds = time.process_time() - cpu_start
        max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        max_rss_mib = max_rss / (1024 * 1024 if sys.platform == "darwin" else 1024)

        return {
            "engine": get_engine_info(),
            "iterations": iterations,
            "warmup": warmup,
            "latency": _summary(samples),
            "wall_seconds": wall_seconds,
            "cpu_seconds": cpu_seconds,
            "max_rss_mib": max_rss_mib,
            "throughput_requests_per_second": iterations / wall_seconds,
            "native_counters": get_native_invocation_stats(),
            "workload": "HTTP/SSE initialize + get_model_status tools/call",
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.iterations < 1 or args.warmup < 0:
        parser.error("iterations must be positive and warmup must be non-negative")

    if args.worker:
        print(json.dumps(asyncio.run(_worker(args.iterations, args.warmup))))
        return

    report = {
        "scope": "real local HTTP/SSE MCP transport and tool call",
        "units": {"latency": "milliseconds", "memory": "MiB"},
        "backends": {
            backend: _run_backend(backend, args.iterations, args.warmup)
            for backend in ("python", "rust")
        },
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
