"""Machine-collected release evidence.

Release evidence is a record of commands that were *actually executed*: every command entry must
carry the exit code the process returned, and test counts are parsed from real pytest output rather
than typed by hand. A hand-written pass/fail claim is documentation, not evidence.

The collector is deliberately stdlib-only and deterministic: the same inputs always serialize to
the same JSON, so release evidence diffs are reviewable.
"""

from __future__ import annotations

import json
import platform
import re
import sys
from collections.abc import Iterable, Mapping
from typing import Any

from marketing_mcp import (
    RUNTIME_DEPENDENCIES,
    __version__,
    _installed_version,
)

EVIDENCE_SCHEMA_VERSION = 1
REDACTION = "***REDACTED***"

#: Environment variable names whose values must never be recorded.
SECRET_ENV_PATTERN = re.compile(
    r"(API[_-]?KEY|SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|PRIVATE[_-]?KEY)",
    re.IGNORECASE,
)

_SECRET_TEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(--api[-_]?key(?:=|\s+))(\S+)", re.IGNORECASE),
    re.compile(r"(--jwt[-_]?secret(?:=|\s+))(\S+)", re.IGNORECASE),
    re.compile(r"([A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|CREDENTIAL)[A-Z0-9_]*=)(\S+)"),
    re.compile(r"([?&](?:token|api_key|access_token)=)([^\s&]+)", re.IGNORECASE),
    re.compile(r"(Bearer\s+)(\S+)", re.IGNORECASE),
)

_PYTEST_COUNT_PATTERN = re.compile(
    r"(?P<count>\d+)\s+(?P<outcome>passed|failed|skipped|error|errors|xfailed|xpassed)"
)

_CI_PROVIDERS: tuple[tuple[str, str, tuple[str, str, str]], ...] = (
    # (env flag, provider name, (run id key, workflow key, sha key))
    ("GITHUB_ACTIONS", "github-actions", ("GITHUB_RUN_ID", "GITHUB_WORKFLOW", "GITHUB_SHA")),
    ("GITLAB_CI", "gitlab-ci", ("CI_PIPELINE_ID", "CI_JOB_NAME", "CI_COMMIT_SHA")),
    ("CIRCLECI", "circleci", ("CIRCLE_BUILD_NUM", "CIRCLE_JOB", "CIRCLE_SHA1")),
)


def redact_secrets(text: str) -> str:
    """Mask credential-shaped substrings in ``text``."""
    redacted = text
    for pattern in _SECRET_TEXT_PATTERNS:
        redacted = pattern.sub(lambda m: f"{m.group(1)}{REDACTION}", redacted)
    return redacted


def parse_pytest_summary(text: str) -> dict[str, int]:
    """Parse a pytest summary line into counts; empty dict when the text is not a summary."""
    counts = {
        "tests_passed": 0,
        "tests_failed": 0,
        "tests_skipped": 0,
        "tests_errors": 0,
    }
    found = False
    for match in _PYTEST_COUNT_PATTERN.finditer(text):
        count = int(match.group("count"))
        outcome = match.group("outcome")
        if outcome == "passed":
            counts["tests_passed"] += count
        elif outcome == "failed":
            counts["tests_failed"] += count
        elif outcome == "skipped":
            counts["tests_skipped"] += count
        elif outcome in {"error", "errors"}:
            counts["tests_errors"] += count
        else:
            continue
        found = True
    return counts if found else {}


def _normalize_command(entry: Mapping[str, Any]) -> dict[str, Any]:
    if not entry.get("command"):
        raise ValueError("release evidence requires a 'command' string for every entry")
    if "exit_code" not in entry:
        raise ValueError(
            f"release evidence requires an observed 'exit_code' for {entry['command']!r}; "
            "a claim without an executed exit code is not evidence"
        )
    exit_code = entry["exit_code"]
    if not isinstance(exit_code, int):
        message = f"exit_code for {entry['command']!r} must be an int, got {exit_code!r}"
        raise TypeError(message)

    stdout_tail = redact_secrets(str(entry.get("stdout_tail", "")))
    record: dict[str, Any] = {
        "command": redact_secrets(str(entry["command"])),
        "exit_code": exit_code,
        "passed_all": exit_code == 0,
        "stdout_tail": stdout_tail,
    }
    record.update(parse_pytest_summary(stdout_tail))
    if "tests_passed" in record and "tests_failed" not in record:  # pragma: no cover - defensive
        record["tests_failed"] = 0
    if "duration_seconds" in entry:
        record["duration_seconds"] = entry["duration_seconds"]
    return record


def _normalize_artifact(entry: Mapping[str, Any]) -> dict[str, Any]:
    missing = {"name", "bytes", "sha256"} - set(entry)
    if missing:
        raise ValueError(f"artifact evidence is missing {sorted(missing)}")
    return {
        "name": str(entry["name"]),
        "bytes": int(entry["bytes"]),
        "sha256": str(entry["sha256"]),
    }


def _ci_provenance(env: Mapping[str, str]) -> dict[str, Any]:
    for flag, provider, (run_id_key, workflow_key, sha_key) in _CI_PROVIDERS:
        if env.get(flag, "").strip().lower() in {"true", "1", "yes"}:
            return {
                "is_ci": True,
                "provider": provider,
                "run_id": env.get(run_id_key) or None,
                "workflow": env.get(workflow_key) or None,
                "reported_commit_sha": env.get(sha_key) or None,
            }
    return {
        "is_ci": False,
        "provider": None,
        "run_id": None,
        "workflow": None,
        "reported_commit_sha": None,
    }


def _safe_env(env: Mapping[str, str]) -> dict[str, str]:
    return {
        key: (REDACTION if SECRET_ENV_PATTERN.search(key) else redact_secrets(str(value)))
        for key, value in sorted(env.items())
    }


def collect_release_evidence(
    commit_sha: str,
    *,
    commands: Iterable[Mapping[str, Any]],
    artifacts: Iterable[Mapping[str, Any]] = (),
    collected_at: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a release evidence object from executed command results.

    Args:
        commit_sha: The commit every command was executed against.
        commands: Executed command records; each needs ``command`` and an observed ``exit_code``.
        artifacts: Build artifacts with ``name``, ``bytes``, and ``sha256``.
        collected_at: ISO-8601 UTC timestamp, supplied by the caller so output is reproducible.
        env: Environment mapping used for CI provenance; secrets are redacted.

    Raises:
        ValueError: If a command record has no command string or no observed exit code.
    """
    environment = dict(env or {})
    command_records = [_normalize_command(entry) for entry in commands]
    artifact_records = [_normalize_artifact(entry) for entry in artifacts]

    return {
        "application_version": __version__,
        "artifacts": artifact_records,
        "ci": _ci_provenance(environment),
        "collected_at": collected_at,
        "commands": command_records,
        "commit_sha": commit_sha,
        "dependencies": {name: _installed_version(name) for name in RUNTIME_DEPENDENCIES},
        "environment": _safe_env(environment),
        "platform": {
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "release": platform.release(),
            "system": platform.system(),
        },
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "verdict": "PASS" if all(c["passed_all"] for c in command_records) else "FAIL",
    }


def evidence_to_json(evidence: Mapping[str, Any]) -> str:
    """Serialize evidence deterministically."""
    return json.dumps(evidence, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def render_release_evidence_markdown(evidence: Mapping[str, Any]) -> str:
    """Render a human-readable summary of a machine-collected evidence object."""
    ci = evidence["ci"]
    origin = f"{ci['provider']} run {ci['run_id']}" if ci["is_ci"] else "local workstation"
    lines = [
        f"# Release evidence — `{evidence['commit_sha']}`",
        "",
        "<!-- GENERATED FILE - machine-collected release evidence. Do not hand-edit results. -->",
        "",
        (
            "This report is machine-collected: every row below records a command that was "
            "executed and the exit code it returned. Hand-edited pass/fail claims are not "
            "release evidence."
        ),
        "",
        f"- **Verdict:** {evidence['verdict']}",
        f"- **Commit:** `{evidence['commit_sha']}`",
        f"- **Collected at:** {evidence['collected_at']}",
        f"- **Collected on:** {origin}",
        f"- **Application version:** {evidence['application_version']}",
        (
            f"- **Platform:** {evidence['platform']['system']} "
            f"{evidence['platform']['release']} ({evidence['platform']['machine']}), "
            f"{evidence['platform']['python_implementation']} "
            f"{evidence['platform']['python_version']}"
        ),
        "",
        "## Dependency versions",
        "",
        "| Package | Version |",
        "|---|---|",
    ]
    for name, version in evidence["dependencies"].items():
        lines.append(f"| `{name}` | {version or 'not installed'} |")

    lines += [
        "",
        "## Executed commands",
        "",
        "| Command | Exit code | Passed | Failed | Skipped | Output tail |",
        "|---|---|---|---|---|---|",
    ]
    for command in evidence["commands"]:
        lines.append(
            f"| `{command['command']}` | {command['exit_code']} "
            f"| {command.get('tests_passed', '-')} "
            f"| {command.get('tests_failed', '-')} "
            f"| {command.get('tests_skipped', '-')} "
            f"| {command['stdout_tail'] or '-'} |"
        )

    if evidence["artifacts"]:
        lines += [
            "",
            "## Build artifacts",
            "",
            "| Artifact | Bytes | SHA-256 |",
            "|---|---|---|",
        ]
        for artifact in evidence["artifacts"]:
            lines.append(
                f"| `{artifact['name']}` | {artifact['bytes']} | `{artifact['sha256']}` |"
            )

    return "\n".join(lines).rstrip("\n") + "\n"


def current_python_command() -> str:  # pragma: no cover - trivial helper for the CLI
    return sys.executable


__all__ = [
    "EVIDENCE_SCHEMA_VERSION",
    "REDACTION",
    "collect_release_evidence",
    "evidence_to_json",
    "parse_pytest_summary",
    "redact_secrets",
    "render_release_evidence_markdown",
]
