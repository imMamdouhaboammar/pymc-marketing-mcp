"""Regression tests for complete, non-duplicative statistical CI shards."""

from __future__ import annotations

import importlib.util
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "statistical.yml"
SCRIPT = REPO_ROOT / "scripts" / "check_statistical_shards.py"
THREAD_ENV = (
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


def _load_checker():
    assert SCRIPT.is_file(), "the statistical shard manifest/checker must exist"
    spec = importlib.util.spec_from_file_location("check_statistical_shards", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_junit(path: Path, *, tests: int = 2, failures: int = 0, seconds: float = 1.25) -> None:
    root = ET.Element(
        "testsuites",
        tests=str(tests),
        failures=str(failures),
        errors="0",
        skipped="0",
        time=str(seconds),
    )
    ET.SubElement(
        root,
        "testcase",
        classname="tests.statistical.test_wrong_module",
        name="test_wrong_node",
    )
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def test_workflow_does_not_run_full_statistical_suite_in_every_matrix_lane() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'uv run pytest -m statistical -v --durations=20' not in workflow
    assert "check_statistical_shards.py selectors" in workflow
    assert '"${selectors[@]}"' in workflow
    assert "< <(" not in workflow
    assert "${#selectors[@]}" in workflow


def test_manifest_partitions_actual_pytest_collection() -> None:
    checker = _load_checker()
    collected = checker.collect_statistical_nodeids(REPO_ROOT)

    summary = checker.validate_shards(collected)

    assert summary["collected"] == len(collected)
    assert summary["assigned"] == len(collected)
    assert summary["duplicates"] == []
    assert all(summary["shard_counts"].values())
    assert any(nodeid.startswith("tests/integration/") for nodeid in collected)
    assert checker.DUPLICATE_ALLOWLIST == frozenset()


def test_manifest_validation_rejects_missing_duplicate_and_empty_shards() -> None:
    checker = _load_checker()

    with pytest.raises(ValueError, match="missing"):
        checker.validate_shards(("a::test_one", "b::test_two"), {"one": ("a::test_one",)})
    with pytest.raises(ValueError, match="duplicate"):
        checker.validate_shards(
            ("a::test_one",), {"one": ("a::test_one",), "two": ("a::test_one",)}
        )
    with pytest.raises(ValueError, match="empty"):
        checker.validate_shards(("a::test_one",), {"one": ("a::test_one",), "two": ()})


def test_workflow_preserves_thread_limits_and_sampling_rigor() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    for variable in THREAD_ENV:
        assert re.search(rf"^  {variable}: [\"']1[\"']$", workflow, re.MULTILINE)
    assert "--durations=20" in workflow
    assert not re.search(r"--(?:draws|tune|chains|cores)(?:=|\s)", workflow)
    assert "collect_release_evidence.py" not in workflow


def test_workflow_uploads_unique_failed_lane_evidence_and_aggregates_fail_closed() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    artifact_name = (
        r"statistical-evidence-\$\{\{ github\.sha \}\}-"
        r"\$\{\{ github\.run_attempt \}\}-\$\{\{ matrix\.shard \}\}"
    )

    assert re.search(artifact_name, workflow)
    assert workflow.count("if: always()") >= 3
    assert "continue-on-error: true" in workflow
    assert "steps.pytest.outcome" in workflow
    assert re.search(r"^  statistical-aggregate:$", workflow, re.MULTILINE)
    assert "needs: statistical-suite" in workflow
    assert "check_statistical_shards.py aggregate" in workflow
    assert "github.sha" in workflow and "github.run_attempt" in workflow


def test_aggregate_rejects_missing_failed_wrong_sha_and_duplicate_records(tmp_path: Path) -> None:
    checker = _load_checker()
    shards = tuple(checker.SHARDS)

    def write_record(shard: str, *, sha: str = "abc", outcome: str = "passed", suffix=""):
        path = tmp_path / f"{shard}{suffix}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "shard": shard,
                    "sha": sha,
                    "run_attempt": "2",
                    "outcome": outcome,
                    "exit_code": 0 if outcome == "passed" else 1,
                    "tests": len(checker.SHARDS[shard]),
                    "failures": 0 if outcome == "passed" else 1,
                    "errors": 0,
                    "skipped": 0,
                    "seconds": 0.5,
                    "nodeids": list(checker.SHARDS[shard]),
                }
            ),
            encoding="utf-8",
        )
        return path

    for shard in shards:
        write_record(shard)
    summary = checker.aggregate_evidence(tmp_path, sha="abc", run_attempt="2")
    assert summary["shards"] == len(shards)

    (tmp_path / f"{shards[0]}.json").unlink()
    with pytest.raises(ValueError, match="missing"):
        checker.aggregate_evidence(tmp_path, sha="abc", run_attempt="2")

    write_record(shards[0], outcome="failed")
    with pytest.raises(ValueError, match="failed"):
        checker.aggregate_evidence(tmp_path, sha="abc", run_attempt="2")

    write_record(shards[0], sha="wrong")
    with pytest.raises(ValueError, match="SHA"):
        checker.aggregate_evidence(tmp_path, sha="abc", run_attempt="2")

    write_record(shards[0])
    write_record(shards[0], suffix="-duplicate")
    with pytest.raises(ValueError, match="duplicate"):
        checker.aggregate_evidence(tmp_path, sha="abc", run_attempt="2")

    (tmp_path / f"{shards[0]}-duplicate.json").unlink()
    record_path = tmp_path / f"{shards[0]}.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["tests"] = 0
    record_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="test count"):
        checker.aggregate_evidence(tmp_path, sha="abc", run_attempt="2")

    record["tests"] = len(checker.SHARDS[shards[0]])
    record["skipped"] = 1
    record_path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="skipped"):
        checker.aggregate_evidence(tmp_path, sha="abc", run_attempt="2")


def test_record_evidence_preserves_failed_pytest_result(tmp_path: Path) -> None:
    checker = _load_checker()
    shard = next(iter(checker.SHARDS))
    junit = tmp_path / "pytest.xml"
    output = tmp_path / "record.json"
    _write_junit(junit, tests=3, failures=1)

    record = checker.write_shard_evidence(
        shard=shard,
        junit_path=junit,
        output_path=output,
        sha="deadbeef",
        run_attempt="4",
        exit_code=1,
    )

    assert output.is_file()
    assert record["outcome"] == "failed"
    assert record["exit_code"] == 1
    assert record["failures"] == 1
    assert record["nodeids"] == [
        "tests/statistical/test_wrong_module.py::test_wrong_node"
    ]
    assert record["sha"] == "deadbeef"
    assert record["run_attempt"] == "4"
