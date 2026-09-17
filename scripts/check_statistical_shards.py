"""Define, verify, and aggregate the statistical pytest shards used by CI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

SHARDS: dict[str, tuple[str, ...]] = {
    "mmm": (
        "tests/integration/test_persistence_lifecycle.py::test_full_persistence_lifecycle_across_restarts",
        "tests/statistical/test_channel_specific_config.py::test_real_channel_specific_adstock_priors",
        "tests/statistical/test_multidimensional_pymc_sampling.py::test_real_multidimensional_mmm_panel_sampling",
        "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_mmm_end_to_end_statistical_workflow",
        "tests/statistical/test_transform_family_sampling.py::test_transform_matrix_sampling_smoke[geometric-4-logistic]",
        "tests/statistical/test_transform_family_sampling.py::test_transform_matrix_sampling_smoke[delayed-4-hill]",
        "tests/statistical/test_transform_family_sampling.py::test_transform_matrix_sampling_smoke[weibull_cdf-4-michaelis_menten]",
        "tests/statistical/test_transform_family_sampling.py::test_transform_matrix_sampling_smoke[none-1-none]",
    ),
    "flighting-budget": (
        "tests/statistical/test_decision_invariants.py::test_zero_spend_change_produces_near_zero_response_change",
        "tests/statistical/test_decision_invariants.py::test_saturated_channel_marginal_below_average_return",
        "tests/statistical/test_decision_invariants.py::test_flighting_respects_conservation_floors_and_caps",
        "tests/statistical/test_flighting_optimization.py::test_real_dynamic_flighting_optimization",
        "tests/statistical/test_flighting_optimization.py::test_flighting_response_matches_official_transform_recomputation",
    ),
    "clv": (
        "tests/statistical/test_clv_real_models.py::test_real_bg_nbd_and_gamma_gamma_workflow",
        "tests/statistical/test_clv_real_models.py::test_real_shifted_beta_geo_workflow",
    ),
    "model-selection": (
        "tests/statistical/test_model_selection_real_idata.py::test_real_arviz_model_comparison_stacking",
        "tests/statistical/test_model_selection_real_idata.py::test_real_arviz_model_comparison_bb_pseudo_bma",
        "tests/statistical/test_model_selection_real_idata.py::test_real_arviz_model_comparison_pseudo_bma",
        "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_time_slice_cross_validation_and_prior_sensitivity",
    ),
    "calibration-lineage": (
        "tests/statistical/test_decision_invariants.py::test_calibration_creates_lineage_without_mutating_parent",
        "tests/statistical/test_decision_invariants.py::test_comparison_rejects_different_fingerprints_despite_forged_ids",
        "tests/statistical/test_real_pymc_sampling.py::test_real_pymc_lift_test_calibration_and_lineage",
    ),
    "serialization-invariants": (
        "tests/statistical/test_decision_invariants.py::test_model_reload_preserves_posterior_summaries",
        "tests/statistical/test_plot_summary_consistency.py::test_plot_summary_matches_analytical_contribution_summary",
        "tests/statistical/test_plot_summary_consistency.py::test_plots_render_against_real_datatree_idata[waterfall_decomposition]",
        "tests/statistical/test_plot_summary_consistency.py::test_plots_render_against_real_datatree_idata[actual_vs_predicted]",
        "tests/statistical/test_plot_summary_consistency.py::test_plots_render_against_real_datatree_idata[channel_contribution_share]",
        "tests/statistical/test_plot_summary_consistency.py::test_plots_render_against_real_datatree_idata[saturation_curves]",
    ),
}

# A node ID may appear in more than one shard only after an explicit, reviewed addition here.
DUPLICATE_ALLOWLIST: frozenset[str] = frozenset()


def _nodeids_from_collection_output(output: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for line in output.splitlines()
        if line.startswith("tests/") and "::" in line
    )


def collect_statistical_nodeids(repo_root: Path) -> tuple[str, ...]:
    """Return the actual repository-wide collection carrying the statistical marker."""
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{repo_root / 'src'}:{env.get('PYTHONPATH', '')}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", "statistical"],
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pytest statistical collection failed ({result.returncode}):\n{result.stdout}{result.stderr}"
        )
    nodeids = _nodeids_from_collection_output(result.stdout)
    if not nodeids:
        raise ValueError("pytest statistical collection is empty")
    return nodeids


def validate_shards(
    collected: Iterable[str],
    shards: Mapping[str, Sequence[str]] = SHARDS,
    duplicate_allowlist: frozenset[str] = DUPLICATE_ALLOWLIST,
) -> dict[str, object]:
    """Fail unless shards are nonempty and exactly cover the collected node IDs."""
    collected_set = set(collected)
    empty = sorted(name for name, nodeids in shards.items() if not nodeids)
    assigned = [nodeid for nodeids in shards.values() for nodeid in nodeids]
    counts = Counter(assigned)
    duplicates = sorted(nodeid for nodeid, count in counts.items() if count > 1)
    unapproved_duplicates = sorted(set(duplicates) - duplicate_allowlist)
    stale_allowlist = sorted(duplicate_allowlist - set(duplicates))
    assigned_set = set(assigned)
    missing = sorted(collected_set - assigned_set)
    unexpected = sorted(assigned_set - collected_set)

    problems = []
    if empty:
        problems.append(f"empty shards: {empty}")
    if missing:
        problems.append(f"missing node IDs: {missing}")
    if unexpected:
        problems.append(f"unexpected node IDs: {unexpected}")
    if unapproved_duplicates:
        problems.append(f"duplicate node IDs: {unapproved_duplicates}")
    if stale_allowlist:
        problems.append(f"duplicate allowlist entries are not duplicated: {stale_allowlist}")
    if problems:
        raise ValueError("; ".join(problems))

    return {
        "collected": len(collected_set),
        "assigned": len(assigned),
        "duplicates": duplicates,
        "shard_counts": {name: len(nodeids) for name, nodeids in shards.items()},
    }


def _junit_root(junit_path: Path) -> ET.Element | None:
    return ET.parse(junit_path).getroot() if junit_path.is_file() else None


def _junit_totals(root: ET.Element | None) -> dict[str, int | float]:
    if root is None:
        return {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "seconds": 0.0}
    suites = [root] if root.tag == "testsuites" else list(root.iter("testsuite"))
    if root.tag == "testsuites" and root.get("tests") is None:
        suites = list(root.iter("testsuite"))
    return {
        "tests": sum(int(suite.get("tests", 0)) for suite in suites),
        "failures": sum(int(suite.get("failures", 0)) for suite in suites),
        "errors": sum(int(suite.get("errors", 0)) for suite in suites),
        "skipped": sum(int(suite.get("skipped", 0)) for suite in suites),
        "seconds": sum(float(suite.get("time", 0.0)) for suite in suites),
    }


def _junit_nodeids(root: ET.Element | None) -> list[str]:
    if root is None:
        return []
    nodeids = []
    for testcase in root.iter("testcase"):
        name = testcase.get("name")
        file_name = testcase.get("file")
        if not file_name:
            classname = testcase.get("classname")
            file_name = f"{classname.replace('.', '/')}.py" if classname else None
        if name and file_name:
            nodeids.append(f"{file_name}::{name}")
    return nodeids


def write_shard_evidence(
    *,
    shard: str,
    junit_path: Path,
    output_path: Path,
    sha: str,
    run_attempt: str,
    exit_code: int,
) -> dict[str, object]:
    """Persist one shard result even when pytest failed before producing JUnit XML."""
    if shard not in SHARDS:
        raise ValueError(f"unknown shard: {shard}")
    junit_root = _junit_root(junit_path)
    record: dict[str, object] = {
        "schema_version": 1,
        "shard": shard,
        "sha": sha,
        "run_attempt": str(run_attempt),
        "outcome": "passed" if exit_code == 0 else "failed",
        "exit_code": exit_code,
        **_junit_totals(junit_root),
        "nodeids": _junit_nodeids(junit_root),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def aggregate_evidence(
    evidence_dir: Path, *, sha: str, run_attempt: str
) -> dict[str, object]:
    """Fail closed unless exactly one passing, correctly attributed record exists per shard."""
    records = [json.loads(path.read_text(encoding="utf-8")) for path in evidence_dir.glob("*.json")]
    by_shard = Counter(str(record.get("shard", "")) for record in records)
    duplicates = sorted(shard for shard, count in by_shard.items() if count > 1)
    expected = set(SHARDS)
    present = set(by_shard)
    missing = sorted(expected - present)
    unexpected = sorted(present - expected)
    if duplicates:
        raise ValueError(f"duplicate shard records: {duplicates}")
    if missing:
        raise ValueError(f"missing shard records: {missing}")
    if unexpected:
        raise ValueError(f"unexpected shard records: {unexpected}")

    for record in records:
        shard = str(record["shard"])
        if record.get("schema_version") != 1:
            raise ValueError(f"wrong evidence schema for shard {shard}")
        if record.get("sha") != sha:
            raise ValueError(f"wrong SHA for shard {shard}: {record.get('sha')!r}")
        if str(record.get("run_attempt")) != str(run_attempt):
            raise ValueError(f"wrong run attempt for shard {shard}: {record.get('run_attempt')!r}")
        if record.get("outcome") != "passed" or record.get("exit_code") != 0:
            raise ValueError(f"failed shard record: {shard}")
        for field in ("failures", "errors", "skipped"):
            if record.get(field) != 0:
                raise ValueError(f"shard {shard} has {record.get(field)!r} {field}")
        if record.get("nodeids") != list(SHARDS[shard]):
            raise ValueError(f"wrong node ID manifest for shard {shard}")
        if record.get("tests") != len(SHARDS[shard]):
            raise ValueError(f"wrong test count for shard {shard}: {record.get('tests')!r}")

    return {
        "schema_version": 1,
        "sha": sha,
        "run_attempt": str(run_attempt),
        "outcome": "passed",
        "shards": len(records),
        "tests": sum(int(record.get("tests", 0)) for record in records),
        "failures": sum(int(record.get("failures", 0)) for record in records),
        "errors": sum(int(record.get("errors", 0)) for record in records),
        "skipped": sum(int(record.get("skipped", 0)) for record in records),
        "seconds": sum(float(record.get("seconds", 0.0)) for record in records),
        "shard_counts": {str(record["shard"]): int(record.get("tests", 0)) for record in records},
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    selectors = subparsers.add_parser("selectors")
    selectors.add_argument("--shard", required=True, choices=SHARDS)
    record = subparsers.add_parser("record")
    record.add_argument("--shard", required=True, choices=SHARDS)
    record.add_argument("--junit", required=True, type=Path)
    record.add_argument("--output", required=True, type=Path)
    record.add_argument("--sha", required=True)
    record.add_argument("--run-attempt", required=True)
    record.add_argument("--exit-code", required=True, type=int)
    aggregate = subparsers.add_parser("aggregate")
    aggregate.add_argument("--evidence-dir", required=True, type=Path)
    aggregate.add_argument("--sha", required=True)
    aggregate.add_argument("--run-attempt", required=True)
    aggregate.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "selectors":
        print("\n".join(SHARDS[args.shard]))
        return 0
    if args.command == "check":
        summary = validate_shards(collect_statistical_nodeids(Path.cwd()))
    elif args.command == "record":
        summary = write_shard_evidence(
            shard=args.shard,
            junit_path=args.junit,
            output_path=args.output,
            sha=args.sha,
            run_attempt=args.run_attempt,
            exit_code=args.exit_code,
        )
    else:
        summary = aggregate_evidence(
            args.evidence_dir, sha=args.sha, run_attempt=args.run_attempt
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
