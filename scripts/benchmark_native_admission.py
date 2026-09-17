"""Repeatable admission benchmark, including the unavoidable SDK re-parse cost.

This does not claim an end-to-end MCP speedup. It measures the incremental cost
of native full framing validation when the Python MCP SDK parses the body again.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from collections.abc import Callable
from typing import Any

from marketing_mcp.accelerators import fast_admit_request, get_engine_info


def _percentile(samples: list[float], quantile: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * quantile))
    return ordered[index]


def _measure(operation: Callable[[], Any], iterations: int) -> dict[str, float]:
    samples: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        operation()
        samples.append((time.perf_counter_ns() - started) / 1_000_000)
    return {
        "p50_ms": statistics.median(samples),
        "p95_ms": _percentile(samples, 0.95),
        "p99_ms": _percentile(samples, 0.99),
        "mean_ms": statistics.fmean(samples),
    }


def _payload(argument_bytes: int) -> bytes:
    return json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "benchmark-1",
            "method": "tools/call",
            "params": {"name": "inspect_dataset", "arguments": {"padding": "x" * argument_bytes}},
        },
        separators=(",", ":"),
    ).encode()


def run(iterations: int) -> dict[str, Any]:
    scenarios: dict[str, Any] = {}
    for argument_bytes in (0, 1_000, 100_000):
        body = _payload(argument_bytes)
        scenarios[str(len(body))] = {
            "python_sdk_parse": _measure(lambda body=body: json.loads(body), iterations),
            "native_admission": _measure(lambda body=body: fast_admit_request(body), iterations),
            "native_then_sdk_parse": _measure(
                lambda body=body: (fast_admit_request(body), json.loads(body)),
                iterations,
            ),
        }
    return {
        "engine": get_engine_info(),
        "iterations": iterations,
        "units": "milliseconds",
        "scope": "admission boundary only; not an end-to-end MCP speedup claim",
        "scenarios_by_payload_bytes": scenarios,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=1_000)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = run(max(10, args.iterations))
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
