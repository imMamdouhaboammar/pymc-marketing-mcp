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

EVIDENCE_SCHEMA_VERSION = 2
REDACTION = "***REDACTED***"

GATE_PROOFS: dict[str, frozenset[str]] = {
    "G0": frozenset({"g0-truth"}),
    "G1": frozenset({"g1-statistical"}),
    "G2": frozenset({"g2-recovery"}),
    "G3": frozenset({"g3-security"}),
    "G4": frozenset({"g4-operability"}),
    "G5": frozenset({"g5-artifacts"}),
    "H0": frozenset({"h0-runtime"}),
    "H1": frozenset({"h1-http-identity"}),
    "H2": frozenset({"h2-isolation"}),
    "H3": frozenset({"h3-credentials"}),
    "H4": frozenset({"h4-worker"}),
    "H5": frozenset({"h5-agent-evals"}),
    "H6": frozenset({"h6-upstream"}),
    "AQG": frozenset({"aqg-agent-quality"}),
}
_ALLOWED_PROOFS = frozenset().union(*GATE_PROOFS.values())
_SAFE_ENV_KEYS = frozenset(
    {
        "CI",
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "PYTHONHASHSEED",
        "RUNNER_ARCH",
        "RUNNER_OS",
    }
)

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

    proofs = entry.get("proofs", ())
    if isinstance(proofs, (str, bytes)) or not isinstance(proofs, Iterable):
        raise TypeError(f"proofs for {entry['command']!r} must be an iterable of proof ids")
    normalized_proofs = sorted({str(proof) for proof in proofs})
    unknown_proofs = set(normalized_proofs) - _ALLOWED_PROOFS
    if unknown_proofs:
        raise ValueError(f"unknown release proof ids: {sorted(unknown_proofs)}")
    record["proofs"] = normalized_proofs
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


def _ci_provenance(env: Mapping[str, str], commit_sha: str) -> dict[str, Any]:
    for flag, provider, (run_id_key, workflow_key, sha_key) in _CI_PROVIDERS:
        if env.get(flag, "").strip().lower() in {"true", "1", "yes"}:
            reported_sha = env.get(sha_key) or None
            return {
                "is_ci": True,
                "provider": provider,
                "run_id": env.get(run_id_key) or None,
                "run_attempt": env.get("GITHUB_RUN_ATTEMPT") or None,
                "workflow": env.get(workflow_key) or None,
                "reported_commit_sha": reported_sha,
                "candidate_matches": bool(reported_sha and reported_sha == commit_sha),
            }
    return {
        "is_ci": False,
        "provider": None,
        "run_id": None,
        "run_attempt": None,
        "workflow": None,
        "reported_commit_sha": None,
        "candidate_matches": False,
    }


def _safe_env(env: Mapping[str, str]) -> dict[str, str]:
    return {
        key: redact_secrets(str(value))
        for key, value in sorted(env.items())
        if key in _SAFE_ENV_KEYS and not SECRET_ENV_PATTERN.search(key)
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

    verdict = (
        "PASS" if command_records and all(c["passed_all"] for c in command_records) else "FAIL"
    )
    ci = _ci_provenance(environment, commit_sha)
    successful_proofs = {
        proof
        for command in command_records
        if command["passed_all"]
        for proof in command["proofs"]
    }
    gate_results = {
        gate: {
            "status": (
                "green"
                if verdict == "PASS"
                and ci["candidate_matches"]
                and required_proofs <= successful_proofs
                else "not_proven"
            ),
            "required_proofs": sorted(required_proofs),
            "observed_proofs": sorted(required_proofs & successful_proofs),
        }
        for gate, required_proofs in GATE_PROOFS.items()
    }
    release_authorized = all(result["status"] == "green" for result in gate_results.values())

    return {
        "application_version": __version__,
        "artifacts": artifact_records,
        "ci": ci,
        "collected_at": collected_at,
        "commands": command_records,
        "commit_sha": commit_sha,
        "dependencies": {name: _installed_version(name) for name in RUNTIME_DEPENDENCIES},
        "environment": _safe_env(environment),
        "gate_results": gate_results,
        "release_authorized": release_authorized,
        "platform": {
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "release": platform.release(),
            "system": platform.system(),
        },
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "verdict": verdict,
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
        f"- **Command verdict:** {evidence['verdict']}",
        f"- **Release authorized:** {'YES' if evidence.get('release_authorized') else 'NO'}",
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
        "## Gate proofs",
        "",
        "| Gate | Status | Required proofs | Observed proofs |",
        "|---|---|---|---|",
    ]
    for gate, result in evidence["gate_results"].items():
        required = ", ".join(result.get("required_proofs", ())) or "-"
        observed = ", ".join(result.get("observed_proofs", ())) or "-"
        lines.append(f"| {gate} | {result['status']} | {required} | {observed} |")

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
