"""Machine-derived production readiness evidence parsing and verification."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

GateStatus = Literal[
    "green",
    "red",
    "partial",
    "blocked",
    "evidence_pending",
    "not_run",
    "not_proven",
    "not_implemented",
    "strong_implementation_evidence_pending",
]

_TABLE_ROW_PATTERN = re.compile(
    r"^\|\s*(?P<gate>[A-Z0-9]+)\s*\|\s*(?P<name>[^|]+?)\s*\|\s*(?P<status>[^|]+?)\s*\|\s*(?P<what_is_true>[^|]*?)\s*\|\s*(?P<blockers>[^|]*?)\s*\|"
)


@dataclass(frozen=True)
class GateEvidence:
    """Represents release-gate readiness evidence."""

    gate: str
    name: str
    status: str
    what_is_true: str = ""
    blockers: str = ""
    commit_sha: str = ""
    evidence_file: str = ""
    tests: tuple[str, ...] = ()

    def validate(self) -> None:
        """Validate integrity constraints for gate evidence."""
        if self.status == "green":
            if not self.commit_sha:
                raise ValueError(f"Gate {self.gate} cannot be green without commit_sha")
            if not self.tests and not self.evidence_file:
                raise ValueError(f"Gate {self.gate} cannot be green without tests or evidence_file")


def render_readiness_table(gates: Sequence[GateEvidence]) -> str:
    """Render markdown table of readiness gates."""
    lines = [
        "| Gate | Name | Current status | What is true today | What still blocks green |",
        "|---|---|---|---|---|",
    ]
    for g in gates:
        status_str = g.status.replace("_", " ")
        lines.append(f"| {g.gate} | {g.name} | {status_str} | {g.what_is_true} | {g.blockers} |")
    return "\n".join(lines)


def parse_readiness_from_doc(doc_text: str) -> list[GateEvidence]:
    """Parse gate rows from markdown table in PRODUCTION-READINESS.md."""
    gates: list[GateEvidence] = []
    for line in doc_text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith(("| Gate", "|---")):
            continue
        match = _TABLE_ROW_PATTERN.match(line)
        if match:
            gate = match.group("gate").strip()
            name = match.group("name").strip()
            status = match.group("status").strip().lower().replace(" ", "_")
            what_is_true = match.group("what_is_true").strip()
            blockers = match.group("blockers").strip()
            gates.append(
                GateEvidence(
                    gate=gate,
                    name=name,
                    status=status,
                    what_is_true=what_is_true,
                    blockers=blockers,
                )
            )
    return gates


def validate_readiness_doc(
    doc_text: str,
    evidence_bundle: Mapping[str, Any],
    *,
    expected_commit_sha: str | None = None,
) -> list[str]:
    """Audit markdown readiness doc against executed evidence bundle.

    Returns a list of violation findings if any gate claims green without machine evidence.
    """
    findings: list[str] = []
    doc_gates = parse_readiness_from_doc(doc_text)
    gate_results = evidence_bundle.get("gate_results", {})
    bundle_verdict = evidence_bundle.get("verdict", "FAIL")
    bundle_commit_sha = evidence_bundle.get("commit_sha")
    ci = evidence_bundle.get("ci", {})

    if expected_commit_sha and bundle_commit_sha != expected_commit_sha:
        findings.append(
            f"Evidence commit {bundle_commit_sha!r} does not match assessed commit "
            f"{expected_commit_sha!r}"
        )

    for g in doc_gates:
        norm_status = g.status.lower().replace(" ", "_")
        if norm_status == "green":
            gate_data = gate_results.get(g.gate, {})
            gate_status = gate_data.get("status", "not_run")
            if gate_status != "green" or bundle_verdict != "PASS":
                findings.append(
                    f"Gate {g.gate} marked green in document, but evidence bundle reports status={gate_status!r} and verdict={bundle_verdict!r}"
                )
            if not ci.get("is_ci") or not ci.get("candidate_matches"):
                findings.append(
                    f"Gate {g.gate} marked green without proof from the trusted CI candidate"
                )

    return findings


__all__ = [
    "GateEvidence",
    "GateStatus",
    "parse_readiness_from_doc",
    "render_readiness_table",
    "validate_readiness_doc",
]
