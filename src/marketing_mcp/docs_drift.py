"""Documentation drift checks.

Documentation is a product surface: a claim about a version, tool, transform, transport, or safety
policy that the code does not implement is a defect, not a typo. Each check below compares
documentation text against the code that would have to be true for the claim to hold.

Two checks rely on explicit machine-readable markers rather than guessing from prose:

```markdown
<!-- drift-check: decision-gated-tools = optimize_budget, optimize_flighting, simulate_budget -->
```

A version reference is accepted when it equals the canonical runtime version, when the line marks
itself as historical, or when it is a worded reference to a dependency version. A `v`-prefixed
number such as `v0.3.0` is always treated as a claim about this project's release.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import get_args

from mcp.shared.uri_template import UriTemplate

from marketing_mcp import __version__
from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.schemas.models import AdstockType, SaturationType

#: Documentation that must describe the current release truthfully.
DOCUMENTED_DOCS: tuple[str, ...] = (
    "AGENTS.md",
    "README.md",
    "docs/API-COMPATIBILITY.md",
    "docs/ARCHITECTURE.md",
    "docs/CAPABILITIES.md",
    "docs/DECISION-INTEGRITY.md",
    "docs/DEPLOYMENT-GCP.md",
    "docs/PRODUCTION-READINESS.md",
    "docs/SECURITY.md",
    "docs/STATISTICAL-SAFETY.md",
    "docs/STATISTICAL-TESTING.md",
    "docs/TOOL-CONTRACTS.md",
)

#: Transports the CLI actually accepts.
SUPPORTED_TRANSPORTS: tuple[str, ...] = ("stdio", "streamable-http")

_HISTORICAL_MARKER = re.compile(
    r"(?i)\b(historical|historic|changelog|previous(?:ly)?|superseded|legacy|deprecated|"
    r"released in|no longer)\b"
)
_DEPENDENCY_MARKER = re.compile(
    r"(?i)(pymc|arviz|pytensor|numpy|pandas|xarray|h5netcdf|pydantic|starlette|uvicorn|"
    r"python|node|npm|mcp sdk|hatchling|ruff|pytest|>=|<=|==|~=|!=)"
)
_VERSION_CLAIM = re.compile(
    r"(?:\bv(?P<v_prefixed>\d+\.\d+\.\d+)\b)"
    r"|(?:(?i:\b(?:version|release)\b)[^\n\d]{0,20}(?P<worded>\d+\.\d+\.\d+)\b)"
)
_TOOL_HEADING = re.compile(r"^#{2,4}\s+`(?P<name>[a-z][a-z0-9_]*)\(")
_TRANSFORM_LINE = re.compile(r"(?i)^\s*[-*]\s*(?P<kind>Adstocks|Saturations)\s*:\s*(?P<body>.+)$")
_BACKTICKED = re.compile(r"`([^`]+)`")
_TRANSPORT_FLAG = re.compile(r"--transport[=\s]+([a-z][a-z0-9-]*)")
_GATE_MARKER = re.compile(
    r"<!--\s*drift-check:\s*decision-gated-tools\s*=\s*(?P<tools>[^>]*?)\s*-->"
)
_RESOURCE_CONTRACT_LINE = re.compile(
    r"^\s*[-*]\s+`(?P<uri>marketing://[a-zA-Z0-9_\-\.\/\{\}]+)`"
)
_DEPENDENCY_TABLE_ROW = re.compile(
    r"^\s*\|\s*`?(?P<pkg>[a-zA-Z0-9_\-\[\]]+)`?\s*\|\s*`(?P<range>[^`]+)`\s*\|\s*(?P<role>[^|]+)\|\s*$"
)


@dataclass(frozen=True)
class DriftFinding:
    """One documentation claim that the code does not support."""

    check: str
    path: str
    line: int
    message: str

    def __str__(self) -> str:  # pragma: no cover - display helper
        return f"{self.path}:{self.line} [{self.check}] {self.message}"


def _tool_names() -> set[str]:
    return {c.name for c in get_capability_inventory() if c.kind == "tool"}


def _resource_names() -> set[str]:
    return {c.name for c in get_capability_inventory() if c.kind == "resource"}


def _resource_discovery_category(uri: str) -> str:
    """Return the MCP discovery surface used by the SDK for a resource URI."""
    return "template" if UriTemplate.parse(uri).variable_names else "static"


def _gated_tools() -> set[str]:
    return {c.name for c in get_capability_inventory() if c.decision_gate_required}


def check_version_references(
    text: str,
    *,
    path: str,
    canonical_version: str = __version__,
) -> list[DriftFinding]:
    """Flag release-version claims that are neither canonical nor marked historical."""
    findings: list[DriftFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if _HISTORICAL_MARKER.search(line):
            continue
        for match in _VERSION_CLAIM.finditer(line):
            version = match.group("v_prefixed") or match.group("worded")
            if version is None or version == canonical_version:
                continue
            # A `v`-prefixed number is always a release claim; a worded reference such as
            # "PyMC-Marketing version 1.0.0" may legitimately describe a dependency.
            if match.group("v_prefixed") is None and _DEPENDENCY_MARKER.search(line):
                continue
            findings.append(
                DriftFinding(
                    check="version-reference",
                    path=path,
                    line=number,
                    message=(
                        f"documents release version {version!r} but the canonical runtime "
                        f"version is {canonical_version!r}; use the canonical version or mark "
                        "the line as historical"
                    ),
                )
            )
    return findings


def check_tool_names(text: str, *, path: str) -> list[DriftFinding]:
    """Flag documented tool headings that no MCP tool implements."""
    known = _tool_names()
    findings: list[DriftFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = _TOOL_HEADING.match(line)
        if match and match.group("name") not in known:
            findings.append(
                DriftFinding(
                    check="tool-name",
                    path=path,
                    line=number,
                    message=(
                        f"documents tool {match.group('name')!r}, which is not in the capability "
                        "inventory"
                    ),
                )
            )
    return findings


def check_transform_vocabulary(text: str, *, path: str) -> list[DriftFinding]:
    """Flag documented adstock/saturation vocabularies that disagree with the schemas."""
    expected = {
        "adstocks": set(get_args(AdstockType)),
        "saturations": set(get_args(SaturationType)),
    }
    findings: list[DriftFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = _TRANSFORM_LINE.match(line)
        if not match:
            continue
        kind = match.group("kind").lower()
        documented = set(_BACKTICKED.findall(match.group("body")))
        unknown = sorted(documented - expected[kind])
        missing = sorted(expected[kind] - documented)
        if unknown:
            findings.append(
                DriftFinding(
                    check="transform-vocabulary",
                    path=path,
                    line=number,
                    message=f"documents unsupported {kind[:-1]} names {unknown}",
                )
            )
        if missing:
            findings.append(
                DriftFinding(
                    check="transform-vocabulary",
                    path=path,
                    line=number,
                    message=f"leaves supported {kind[:-1]} names undocumented: {missing}",
                )
            )
    return findings


def check_transport_names(text: str, *, path: str) -> list[DriftFinding]:
    """Flag documented `--transport` values the CLI would reject."""
    findings: list[DriftFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for transport in _TRANSPORT_FLAG.findall(line):
            if transport not in SUPPORTED_TRANSPORTS:
                findings.append(
                    DriftFinding(
                        check="transport-name",
                        path=path,
                        line=number,
                        message=(
                            f"documents transport {transport!r}; the CLI accepts "
                            f"{list(SUPPORTED_TRANSPORTS)}"
                        ),
                    )
                )
    return findings


def check_decision_gate_claims(text: str, *, path: str) -> list[DriftFinding]:
    """Flag a decision-gate marker that disagrees with the enforced gate policy."""
    findings: list[DriftFinding] = []
    enforced = _gated_tools()
    for number, line in enumerate(text.splitlines(), start=1):
        match = _GATE_MARKER.search(line)
        if not match:
            continue
        claimed = {token.strip() for token in match.group("tools").split(",") if token.strip()}
        if claimed != enforced:
            findings.append(
                DriftFinding(
                    check="decision-gate-claim",
                    path=path,
                    line=number,
                    message=(
                        f"claims decision-gated tools {sorted(claimed)} but the code enforces "
                        f"{sorted(enforced)}"
                    ),
                )
            )
    return findings


def check_resource_contracts(
    text: str,
    *,
    path: str,
    canonical_resources: set[str] | None = None,
) -> list[DriftFinding]:
    """Flag resource-name, completeness, and MCP discovery-category drift."""
    if not path.endswith("TOOL-CONTRACTS.md"):
        return []

    known = canonical_resources if canonical_resources is not None else _resource_names()
    findings: list[DriftFinding] = []
    documented: set[str] = set()
    section: str | None = None

    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped == "### Resource templates":
            section = "template"
            continue
        if stripped == "### Static resources":
            section = "static"
            continue
        if stripped.startswith("### "):
            section = None

        match = _RESOURCE_CONTRACT_LINE.match(line)
        if not match:
            continue
        uri = match.group("uri")
        documented.add(uri)
        if uri not in known:
            findings.append(
                DriftFinding(
                    check="resource-name",
                    path=path,
                    line=number,
                    message=(
                        f"documents resource {uri!r}, which is not in the canonical "
                        "capability registry"
                    ),
                )
            )
            continue

        expected_section = _resource_discovery_category(uri)
        if section != expected_section:
            expected_call = (
                "list_resource_templates()" if expected_section == "template" else "list_resources()"
            )
            actual_label = (
                "Resource templates"
                if section == "template"
                else "Static resources"
                if section == "static"
                else "neither discovery section"
            )
            findings.append(
                DriftFinding(
                    check="resource-category",
                    path=path,
                    line=number,
                    message=(
                        f"documents resource {uri!r} under {actual_label}; MCP SDK "
                        f"registration exposes it through {expected_call}"
                    ),
                )
            )

    missing = sorted(known - documented)
    if missing:
        findings.append(
            DriftFinding(
                check="resource-contract",
                path=path,
                line=1,
                message=f"leaves canonical MCP resources undocumented: {missing}",
            )
        )

    return findings


def _canonical_dependencies(pyproject_path: Path | None = None) -> dict[str, str]:
    import tomllib

    target = pyproject_path or (Path(__file__).resolve().parents[2] / "pyproject.toml")
    if not target.exists():
        return {}
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    project = data.get("project", {})
    deps: dict[str, str] = {}
    requires_python = project.get("requires-python")
    if requires_python:
        deps["Python"] = requires_python
    for item in project.get("dependencies", []):
        m = re.match(r"^([a-zA-Z0-9_\-\[\]]+)(.*)$", item)
        if m:
            deps[m.group(1)] = m.group(2)
    return deps


def check_dependency_ranges(
    text: str,
    *,
    path: str,
    canonical_dependencies: dict[str, str] | None = None,
) -> list[DriftFinding]:
    """Flag documented dependency range drift in API compatibility documentation."""
    if not path.endswith("API-COMPATIBILITY.md"):
        return []

    canonical = (
        canonical_dependencies
        if canonical_dependencies is not None
        else _canonical_dependencies()
    )
    if not canonical:
        return []

    findings: list[DriftFinding] = []
    documented: dict[str, str] = {}

    for number, line in enumerate(text.splitlines(), start=1):
        match = _DEPENDENCY_TABLE_ROW.match(line)
        if not match:
            continue
        pkg = match.group("pkg")
        range_claim = match.group("range")
        if pkg not in canonical:
            findings.append(
                DriftFinding(
                    check="dependency-name",
                    path=path,
                    line=number,
                    message=(
                        f"documents package {pkg!r}, which is absent from the canonical "
                        "direct dependencies in pyproject.toml"
                    ),
                )
            )
            continue

        documented[pkg] = range_claim
        if range_claim != canonical[pkg]:
            findings.append(
                DriftFinding(
                    check="dependency-range",
                    path=path,
                    line=number,
                    message=(
                        f"documents package {pkg!r} with range {range_claim!r}; "
                        f"canonical range in pyproject.toml is {canonical[pkg]!r}"
                    ),
                )
            )

    missing = sorted(set(canonical) - set(documented))
    if missing:
        findings.append(
            DriftFinding(
                check="dependency-completeness",
                path=path,
                line=1,
                message=f"leaves canonical dependencies undocumented in API compatibility table: {missing}",
            )
        )

    return findings


_CHECKS = (
    check_version_references,
    check_tool_names,
    check_transform_vocabulary,
    check_transport_names,
    check_decision_gate_claims,
    check_resource_contracts,
    check_dependency_ranges,
)


def check_docs(root: Path, docs: tuple[str, ...] | None = None) -> list[DriftFinding]:
    """Run every drift check over the documented surface, ordered by path then line."""
    findings: list[DriftFinding] = []
    candidates = docs if docs is not None else DOCUMENTED_DOCS
    canonical_dependencies = _canonical_dependencies(root / "pyproject.toml")
    for relative in candidates:
        path = root / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for check in _CHECKS:
            if check is check_dependency_ranges:
                findings.extend(
                    check_dependency_ranges(
                        text,
                        path=relative,
                        canonical_dependencies=canonical_dependencies,
                    )
                )
            else:
                findings.extend(check(text, path=relative))
    return sorted(findings, key=lambda f: (f.path, f.line, f.check))


def discover_docs(root: Path) -> tuple[str, ...]:
    """Find documentation files to check when the declared set is not available."""
    found = ["README.md"] if (root / "README.md").exists() else []
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        found += sorted(f"docs/{p.name}" for p in docs_dir.glob("*.md"))
    return tuple(found)


__all__ = [
    "DOCUMENTED_DOCS",
    "SUPPORTED_TRANSPORTS",
    "DriftFinding",
    "check_decision_gate_claims",
    "check_dependency_ranges",
    "check_docs",
    "check_resource_contracts",
    "check_tool_names",
    "check_transform_vocabulary",
    "check_transport_names",
    "check_version_references",
    "discover_docs",
]
