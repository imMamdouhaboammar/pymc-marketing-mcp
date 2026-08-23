"""Tests for the release evidence collector.

Task 3 contract: release evidence is machine-collected, deterministic, redacted, and cannot record
a pass/fail claim that was not actually executed.
"""

from __future__ import annotations

import json

import pytest

from marketing_mcp.release_evidence import (
    EVIDENCE_SCHEMA_VERSION,
    collect_release_evidence,
    evidence_to_json,
    parse_pytest_summary,
    redact_secrets,
    render_release_evidence_markdown,
)

COMMIT = "8f7e2a9a03b4d0d580e43eb21270e917953e0b11"

COMMANDS = [
    {
        "command": "uv run pytest -n auto -q -m 'not statistical'",
        "exit_code": 0,
        "stdout_tail": "179 passed, 4 warnings in 24.99s",
    },
    {
        "command": "uv run ruff check src tests",
        "exit_code": 0,
        "stdout_tail": "All checks passed!",
    },
]

ARTIFACTS = [
    {
        "name": "pymc_marketing_mcp-0.4.0-py3-none-any.whl",
        "bytes": 66567,
        "sha256": "d85371739d1a3bfbebdf1ec37c808b69c9cfcd2477f5f50745a635e7d3051b76",
    }
]


def _evidence(**overrides):
    kwargs = {
        "commit_sha": COMMIT,
        "commands": COMMANDS,
        "artifacts": ARTIFACTS,
        "collected_at": "2026-08-23T00:00:00Z",
        "env": {},
    }
    kwargs.update(overrides)
    return collect_release_evidence(**kwargs)


def test_evidence_records_identity_and_schema_version():
    evidence = _evidence()
    assert evidence["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert evidence["commit_sha"] == COMMIT
    assert evidence["collected_at"] == "2026-08-23T00:00:00Z"


def test_evidence_records_platform_and_dependency_versions():
    evidence = _evidence()
    assert evidence["platform"]["python_version"]
    assert evidence["platform"]["system"]
    assert "pymc-marketing" in evidence["dependencies"]
    assert "mcp" in evidence["dependencies"]
    assert evidence["application_version"]


def test_evidence_serialization_is_deterministic():
    first = evidence_to_json(_evidence())
    second = evidence_to_json(_evidence())
    assert first == second
    assert json.loads(first) == json.loads(second)
    keys = list(json.loads(first).keys())
    assert keys == sorted(keys), "top-level keys must be sorted for stable diffs"


def test_command_without_an_exit_code_is_rejected():
    with pytest.raises(ValueError, match="exit_code"):
        _evidence(commands=[{"command": "uv run pytest", "stdout_tail": "179 passed"}])


def test_command_without_a_command_string_is_rejected():
    with pytest.raises(ValueError, match="command"):
        _evidence(commands=[{"exit_code": 0}])


def test_test_counts_are_parsed_from_real_pytest_output_not_asserted_by_hand():
    evidence = _evidence()
    pytest_command = evidence["commands"][0]
    assert pytest_command["tests_passed"] == 179
    assert pytest_command["tests_failed"] == 0
    assert pytest_command["passed_all"] is True


def test_parse_pytest_summary_reads_failures_and_skips():
    parsed = parse_pytest_summary("1 failed, 144 passed, 2 skipped in 77.23s")
    assert parsed == {"tests_passed": 144, "tests_failed": 1, "tests_skipped": 2, "tests_errors": 0}


def test_parse_pytest_summary_returns_empty_for_unparseable_output():
    assert parse_pytest_summary("All checks passed!") == {}


def test_secrets_in_commands_are_redacted():
    evidence = _evidence(
        commands=[
            {
                "command": "marketing-mcp --transport http --api-key sk-live-abcdef123456",
                "exit_code": 0,
                "stdout_tail": "listening",
            }
        ]
    )
    recorded = evidence_to_json(evidence)
    assert "sk-live-abcdef123456" not in recorded
    assert "REDACTED" in recorded


def test_secret_environment_values_are_redacted():
    evidence = _evidence(
        env={
            "MARKETING_MCP_API_KEY": "super-secret-key",
            "MARKETING_MCP_JWT_SECRET": "jwt-secret-value",
            "GITHUB_RUN_ID": "12345",
        }
    )
    recorded = evidence_to_json(evidence)
    assert "super-secret-key" not in recorded
    assert "jwt-secret-value" not in recorded
    assert "12345" in recorded


@pytest.mark.parametrize(
    "text,secret",
    [
        ("--api-key sk-live-999", "sk-live-999"),
        ("MARKETING_MCP_API_KEY=hunter2", "hunter2"),
        ("GET /mcp?token=eyJhbGciOi", "eyJhbGciOi"),
        ("Authorization: Bearer eyJhbGciOiJIUzI1", "eyJhbGciOiJIUzI1"),
    ],
)
def test_redact_secrets_masks_known_credential_shapes(text, secret):
    redacted = redact_secrets(text)
    assert secret not in redacted
    assert "REDACTED" in redacted


def test_redact_secrets_leaves_ordinary_text_untouched():
    text = "uv run pytest -n auto -q -m 'not statistical'"
    assert redact_secrets(text) == text


def test_artifact_hashes_are_preserved():
    evidence = _evidence()
    assert evidence["artifacts"][0]["sha256"].startswith("d853717")
    assert evidence["artifacts"][0]["bytes"] == 66567


def test_markdown_summary_is_generated_from_the_evidence_object():
    evidence = _evidence()
    markdown = render_release_evidence_markdown(evidence)
    assert COMMIT in markdown
    assert "uv run ruff check src tests" in markdown
    assert "179" in markdown
    assert "pymc_marketing_mcp-0.4.0-py3-none-any.whl" in markdown
    assert "machine-collected" in markdown.lower()


def test_markdown_summary_reports_overall_verdict():
    passing = render_release_evidence_markdown(_evidence())
    assert "PASS" in passing

    failing = render_release_evidence_markdown(
        _evidence(
            commands=[
                {
                    "command": "uv run pytest -q",
                    "exit_code": 1,
                    "stdout_tail": "1 failed, 144 passed in 77.23s",
                }
            ]
        )
    )
    assert "FAIL" in failing


def test_ci_provenance_is_captured_when_present():
    evidence = _evidence(
        env={
            "GITHUB_ACTIONS": "true",
            "GITHUB_RUN_ID": "987654",
            "GITHUB_WORKFLOW": "ci",
            "GITHUB_SHA": COMMIT,
        }
    )
    assert evidence["ci"]["is_ci"] is True
    assert evidence["ci"]["provider"] == "github-actions"
    assert evidence["ci"]["run_id"] == "987654"


def test_local_runs_are_labelled_as_not_ci():
    evidence = _evidence()
    assert evidence["ci"]["is_ci"] is False
    assert evidence["ci"]["provider"] is None
    markdown = render_release_evidence_markdown(evidence)
    assert "local" in markdown.lower()


def test_collector_script_records_real_command_outcomes(tmp_path):
    """The CLI must execute commands and persist both JSON and Markdown evidence."""
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "collect_release_evidence.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--output-dir",
            str(tmp_path),
            "--label",
            "smoke",
            "--command",
            f"{sys.executable} -c \"print('7 passed in 0.01s')\"",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    evidence = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
    assert evidence["verdict"] == "PASS"
    assert evidence["commands"][0]["exit_code"] == 0
    assert evidence["commands"][0]["tests_passed"] == 7
    assert evidence["commit_sha"] != "unknown"
    assert "machine-collected" in (tmp_path / "smoke.md").read_text(encoding="utf-8").lower()


def test_collector_script_reports_failure_verdict(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "collect_release_evidence.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--output-dir",
            str(tmp_path),
            "--label",
            "failing",
            "--command",
            f"{sys.executable} -c \"raise SystemExit(3)\"",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    evidence = json.loads((tmp_path / "failing.json").read_text(encoding="utf-8"))
    assert evidence["verdict"] == "FAIL"
    assert evidence["commands"][0]["exit_code"] == 3
