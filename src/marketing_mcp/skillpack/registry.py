"""Canonical Skill Pack loading, validation, routing, and coverage checks."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from marketing_mcp.capabilities import Capability, get_capability_inventory
from marketing_mcp.errors import DomainError

EXPECTED_SHARED_REFERENCES = (
    "scientific-answer-contract",
    "scientific-source-ledger",
)

EXPECTED_SKILLS = (
    "pymc-artifact-delivery",
    "pymc-budget-optimization",
    "pymc-clv-customer-analytics",
    "pymc-dataset-readiness",
    "pymc-diagnostics-gate",
    "pymc-incrementality-evidence",
    "pymc-job-resilience",
    "pymc-lift-calibration",
    "pymc-marketing-router",
    "pymc-mmm-workflow",
    "pymc-model-validation",
)

KNOWN_GATES = frozenset(
    {
        "dataset_validation_passed",
        "diagnostic_gate",
        "calibrated_child_rediagnosed",
        "same_dataset_comparison",
        "artifact_exists",
    }
)
_WORD = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")
_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_STOPWORDS = frozenset(
    {"the", "and", "for", "with", "from", "this", "that", "model", "pymc", "marketing"}
)


class ManifestFiles(BaseModel):
    references: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    templates: list[str] = Field(default_factory=list)
    evals: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)


class ForbiddenRule(BaseModel):
    operations: list[str]
    until: str


class SkillManifest(BaseModel):
    schema_version: Literal["1"] = "1"
    name: str
    version: str
    domain: str
    summary: str
    triggers: list[str] = Field(min_length=1)
    negative_triggers: list[str] = Field(default_factory=list)
    primary_tools: list[str] = Field(default_factory=list)
    secondary_tools: list[str] = Field(default_factory=list)
    deprecated_tools: list[str] = Field(default_factory=list)
    administrative_tools: list[str] = Field(default_factory=list)
    required_resources: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    gates: list[str] = Field(default_factory=list)
    forbidden_before: list[ForbiddenRule] = Field(default_factory=list)
    fallback_skills: list[str] = Field(default_factory=list)
    continuations: list[str] = Field(default_factory=list)
    maturity: Literal["stable", "experimental", "deprecated"] = "stable"
    authoritative_sources: list[str] = Field(default_factory=list)
    files: ManifestFiles = Field(default_factory=ManifestFiles)


class RoutingCase(BaseModel):
    id: str
    type: Literal["should_trigger", "should_not_trigger", "ambiguous", "multi_intent", "recovery"]
    query: str
    expected_skill: str | None = None
    expected_behavior: str | None = None


class ToolTrace(BaseModel):
    id: str
    expected_valid: bool
    max_consecutive_polls: int | None = Field(default=None, ge=1)
    steps: list[dict[str, Any]] = Field(min_length=1)


class SkillEvalFile(BaseModel):
    schema_version: Literal["1"] = "1"
    routing_cases: list[RoutingCase] = Field(min_length=1)
    tool_traces: list[ToolTrace] = Field(default_factory=list)


@dataclass(frozen=True)
class SkillRecord:
    manifest: SkillManifest
    markdown: str
    content_hash: str
    package_dir: Path | None = None


@dataclass(frozen=True)
class CoverageReport:
    errors: tuple[str, ...]
    classification: dict[str, dict[str, Any]]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _record_hash(markdown: str, manifest: SkillManifest) -> str:
    payload = markdown + "\n" + _canonical_json(manifest.model_dump(mode="json"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _frontmatter(markdown: str) -> dict[str, str]:
    if not markdown.startswith("---\n"):
        return {}
    _, body, _ = markdown.split("---", 2)
    result: dict[str, str] = {}
    for raw in body.splitlines():
        if ":" not in raw or raw.startswith((" ", "\t")):
            continue
        key, value = raw.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


class SkillRegistry:
    def __init__(
        self,
        records: Iterable[SkillRecord],
        shared_references: dict[str, str] | None = None,
    ):
        materialized = tuple(records)
        mapping = {record.manifest.name: record for record in materialized}
        if len(mapping) != len(materialized):
            raise ValueError("duplicate skill names")
        self._records = dict(sorted(mapping.items()))
        self._shared_references = dict(sorted((shared_references or {}).items()))

    @classmethod
    def from_source_tree(cls, root: Path | None = None) -> SkillRegistry:
        root = root or _repo_root()
        skills_root = root / ".agents" / "skills"
        records: list[SkillRecord] = []
        for name in EXPECTED_SKILLS:
            package_dir = skills_root / name
            manifest_path = package_dir / "skill.package.json"
            skill_path = package_dir / "SKILL.md"
            if not manifest_path.is_file() or not skill_path.is_file():
                raise ValueError(f"missing canonical skill package: {name}")
            manifest = SkillManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            markdown = skill_path.read_text(encoding="utf-8")
            records.append(
                SkillRecord(manifest, markdown, _record_hash(markdown, manifest), package_dir)
            )
        references_root = root / ".agents" / "references"
        shared_references = {}
        for name in EXPECTED_SHARED_REFERENCES:
            path = references_root / f"{name}.md"
            if not path.is_file():
                raise ValueError(f"missing shared scientific reference: {name}")
            shared_references[name] = path.read_text(encoding="utf-8")
        return cls(records, shared_references)

    @classmethod
    def from_bundle(cls) -> SkillRegistry:
        payload = json.loads(
            resources.files("marketing_mcp.skillpack").joinpath("skill-bundle.json").read_text()
        )
        records = []
        for item in payload["skills"]:
            manifest = SkillManifest.model_validate(item["manifest"])
            markdown = item["markdown"]
            records.append(SkillRecord(manifest, markdown, _record_hash(markdown, manifest)))
        return cls(records, payload.get("references", {}))

    @classmethod
    def runtime(cls) -> SkillRegistry:
        try:
            return cls.from_bundle()
        except (FileNotFoundError, ModuleNotFoundError):
            return cls.from_source_tree()

    def names(self) -> tuple[str, ...]:
        return tuple(self._records)

    def manifests(self) -> tuple[SkillManifest, ...]:
        return tuple(record.manifest for record in self._records.values())

    def shared_reference_names(self) -> tuple[str, ...]:
        return tuple(self._shared_references)

    def get_reference(self, name: str) -> str:
        content = self._shared_references.get(name)
        if content is None:
            raise DomainError(
                "SKILL_REFERENCE_NOT_FOUND",
                f"Unknown shared skill reference '{name}'",
                evidence={"reference_name": name, "allowed": list(self.shared_reference_names())},
            )
        return content

    def get(self, name: str) -> SkillRecord:
        record = self._records.get(name)
        if record is None:
            raise DomainError(
                "SKILL_NOT_FOUND",
                f"Unknown skill '{name}'",
                evidence={"skill_name": name, "allowed": list(self.names())},
                next_action="Read marketing://skills or call get_skill_guidance with a task",
            )
        return record

    def catalog(self) -> dict[str, Any]:
        entries = []
        for record in self._records.values():
            manifest = record.manifest
            entries.append(
                {
                    "name": manifest.name,
                    "version": manifest.version,
                    "summary": manifest.summary,
                    "triggers": manifest.triggers,
                    "primary_tools": manifest.primary_tools,
                    "maturity": manifest.maturity,
                    "resource_uri": f"marketing://skills/{manifest.name}",
                    "manifest_uri": f"marketing://skills/{manifest.name}/manifest",
                    "content_hash": record.content_hash,
                }
            )
        references = [
            {
                "name": name,
                "resource_uri": f"marketing://skills/references/{name}",
                "content_hash": hashlib.sha256(self._shared_references[name].encode()).hexdigest(),
            }
            for name in self.shared_reference_names()
        ]
        catalog_hash = hashlib.sha256(_canonical_json([entries, references]).encode()).hexdigest()
        return {
            "schema_version": "1",
            "catalog_hash": catalog_hash,
            "skills": entries,
            "shared_references": references,
        }

    def catalog_json(self) -> str:
        return json.dumps(self.catalog(), indent=2, ensure_ascii=False)

    def bundle_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "catalog_hash": self.catalog()["catalog_hash"],
            "skills": [
                {
                    "manifest": record.manifest.model_dump(mode="json"),
                    "markdown": record.markdown,
                    "content_hash": record.content_hash,
                }
                for record in self._records.values()
            ],
            "references": self._shared_references,
        }

    def manifest_json(self, name: str) -> str:
        return json.dumps(self.get(name).manifest.model_dump(mode="json"), indent=2)

    def tool_map(self) -> dict[str, Any]:
        report = validate_tool_coverage(self.manifests(), get_capability_inventory())
        return {
            "schema_version": "1",
            "errors": list(report.errors),
            "tools": report.classification,
        }

    def workflow_map(self) -> dict[str, Any]:
        return {
            "schema_version": "1",
            "workflows": [
                {
                    "skill": manifest.name,
                    "prerequisites": manifest.prerequisites,
                    "gates": manifest.gates,
                    "forbidden_before": [r.model_dump() for r in manifest.forbidden_before],
                    "continuations": manifest.continuations,
                    "fallback_skills": manifest.fallback_skills,
                }
                for manifest in self.manifests()
            ],
        }

    def decision_gates(self) -> dict[str, Any]:
        gated = sorted(
            cap.name
            for cap in get_capability_inventory()
            if cap.kind == "tool" and cap.decision_gate_required
        )
        return {
            "schema_version": "1",
            "decision_gated_tools": gated,
            "rule": "A rejected model cannot be used by server-blocked decision operations.",
            "diagnose_tool": "diagnose_mmm",
        }

    def resolve_guidance(
        self, task: str | None = None, skill_name: str | None = None
    ) -> tuple[str, SkillRecord, list[tuple[str, int]]]:
        """Resolve one model-callable guidance request through the validated registry."""
        if skill_name:
            return "fetch", self.get(skill_name), []
        if not task or not task.strip():
            raise DomainError(
                "INPUT_INVALID",
                "Provide either a task to route or an exact skill_name to fetch.",
                next_action="Read marketing://skills for available skill names",
            )
        record, alternatives = self.recommend(task)
        return "route", record, alternatives

    def recommend(self, task: str) -> tuple[SkillRecord, list[tuple[str, int]]]:
        query = task.casefold()
        query_tokens = set(_WORD.findall(query)) - _STOPWORDS
        scored: list[tuple[str, int]] = []
        for record in self._records.values():
            manifest = record.manifest
            score = 0
            for trigger in manifest.triggers:
                phrase = trigger.casefold()
                if phrase in query:
                    score += 12
                score += 2 * len((set(_WORD.findall(phrase)) - _STOPWORDS) & query_tokens)
            for negative in manifest.negative_triggers:
                phrase = negative.casefold()
                if phrase in query:
                    score -= 16
                score -= len((set(_WORD.findall(phrase)) - _STOPWORDS) & query_tokens)
            if manifest.name == "pymc-marketing-router":
                score -= 2
            scored.append((manifest.name, score))
        scored.sort(key=lambda item: (-item[1], item[0]))
        best_name, best_score = scored[0]
        if best_score <= 0:
            best_name = "pymc-marketing-router"
        return self.get(best_name), scored[:3]

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.names() != EXPECTED_SKILLS:
            errors.append(f"skill taxonomy mismatch: {self.names()!r}")
        capabilities = get_capability_inventory()
        tool_names = {cap.name for cap in capabilities if cap.kind == "tool"}
        resource_names = {cap.name for cap in capabilities if cap.kind == "resource"}
        for record in self._records.values():
            errors.extend(self._validate_record(record, tool_names, resource_names))
        errors.extend(validate_tool_coverage(self.manifests(), capabilities).errors)
        return errors

    def _validate_record(
        self, record: SkillRecord, tool_names: set[str], resource_names: set[str]
    ) -> list[str]:
        manifest = record.manifest
        errors: list[str] = []
        frontmatter = _frontmatter(record.markdown)
        if frontmatter.get("name") != manifest.name:
            errors.append(f"{manifest.name}: SKILL frontmatter name does not match manifest")
        if frontmatter.get("version") != manifest.version:
            errors.append(f"{manifest.name}: SKILL frontmatter version does not match manifest")
        description = frontmatter.get("description", "")
        if not description:
            errors.append(f"{manifest.name}: SKILL frontmatter description is required")
        elif not description.startswith("Use when"):
            errors.append(f"{manifest.name}: SKILL frontmatter description must start with 'Use when'")
        for gate in manifest.gates:
            if gate not in KNOWN_GATES:
                errors.append(f"{manifest.name}: unknown gate {gate!r}")
        for rule in manifest.forbidden_before:
            if rule.until not in KNOWN_GATES:
                errors.append(f"{manifest.name}: forbidden_before references unknown gate {rule.until!r}")
        for skill in [*manifest.fallback_skills, *manifest.continuations]:
            if skill not in EXPECTED_SKILLS:
                errors.append(f"{manifest.name}: references unknown skill {skill!r}")
        for resource_name in manifest.required_resources:
            if resource_name not in resource_names:
                errors.append(f"{manifest.name}: unknown resource {resource_name!r}")
        if record.package_dir is None:
            return errors
        listed = manifest.files.model_dump()
        for group, paths in listed.items():
            for relative in paths:
                target = record.package_dir / relative
                if not target.is_file():
                    errors.append(f"{manifest.name}: missing {group} file {relative!r}")
                    continue
                if target.suffix == ".json":
                    try:
                        data = json.loads(target.read_text(encoding="utf-8"))
                        if group == "evals":
                            eval_file = SkillEvalFile.model_validate(data)
                            for case in eval_file.routing_cases:
                                if case.expected_skill and case.expected_skill not in EXPECTED_SKILLS:
                                    errors.append(
                                        f"{manifest.name}: eval {case.id!r} references unknown skill "
                                        f"{case.expected_skill!r}"
                                    )
                            for trace in eval_file.tool_traces:
                                for step in trace.steps:
                                    tool = step.get("tool")
                                    if tool and tool not in tool_names:
                                        errors.append(
                                            f"{manifest.name}: eval trace {trace.id!r} references "
                                            f"unknown MCP tool {tool!r}"
                                        )
                    except (json.JSONDecodeError, ValueError) as exc:
                        errors.append(f"{manifest.name}: invalid {group} JSON {relative!r}: {exc}")
                elif target.suffix == ".py":
                    try:
                        ast.parse(target.read_text(encoding="utf-8"))
                    except SyntaxError as exc:
                        errors.append(f"{manifest.name}: invalid Python {relative!r}: {exc}")
        for path in record.package_dir.rglob("*"):
            if path.is_dir() and not any(path.iterdir()):
                errors.append(f"{manifest.name}: empty support directory {path.relative_to(record.package_dir)}")
        for link in _LINK.findall(record.markdown):
            if link.startswith(("http://", "https://", "marketing://", "#")):
                continue
            target = (record.package_dir / link.split("#", 1)[0]).resolve()
            if not target.exists():
                errors.append(f"{manifest.name}: unresolved local link {link!r}")
        for source in manifest.authoritative_sources:
            if source.startswith(("http://", "https://", "marketing://")):
                continue
            target = (record.package_dir / source).resolve()
            if not target.exists():
                errors.append(f"{manifest.name}: unresolved authoritative source {source!r}")
        return errors


def validate_tool_coverage(
    manifests: Iterable[SkillManifest], capabilities: Iterable[Capability]
) -> CoverageReport:
    manifests = tuple(manifests)
    tool_caps = {cap.name: cap for cap in capabilities if cap.kind == "tool"}
    refs: dict[str, list[tuple[str, str]]] = {}
    categories = (
        ("primary", "primary_tools"),
        ("secondary", "secondary_tools"),
        ("deprecated", "deprecated_tools"),
        ("administrative", "administrative_tools"),
    )
    for manifest in manifests:
        for category, field in categories:
            for tool in getattr(manifest, field):
                refs.setdefault(tool, []).append((manifest.name, category))

    errors: list[str] = []
    result: dict[str, dict[str, Any]] = {}
    for tool in sorted(refs):
        if tool not in tool_caps:
            errors.append(f"skill manifests reference nonexistent MCP tool {tool!r}")
            continue
        categories_seen = {category for _, category in refs[tool]}
        if len(categories_seen) != 1:
            errors.append(f"{tool}: appears in multiple coverage classes {sorted(categories_seen)}")
            continue
        category = next(iter(categories_seen))
        owners = sorted({skill for skill, _ in refs[tool]})
        if category == "primary" and len(owners) != 1:
            errors.append(f"{tool}: primary tool must have exactly one owning skill")
        if tool_caps[tool].status == "deprecated" and category != "deprecated":
            errors.append(f"{tool}: deprecated capability must be classified as deprecated")
        if category == "deprecated" and tool_caps[tool].status != "deprecated":
            errors.append(f"{tool}: non-deprecated capability cannot be classified as deprecated")
        result[tool] = {
            "classification": category,
            "skills": owners,
            "maturity": tool_caps[tool].status,
            "decision_gate_required": tool_caps[tool].decision_gate_required,
        }
    for tool in sorted(set(tool_caps) - set(refs)):
        errors.append(f"public MCP tool has no Skill guidance classification: {tool}")
    return CoverageReport(tuple(sorted(errors)), result)


@lru_cache(maxsize=1)
def get_runtime_registry() -> SkillRegistry:
    """Load the immutable Skill registry once per server process."""
    return SkillRegistry.runtime()
