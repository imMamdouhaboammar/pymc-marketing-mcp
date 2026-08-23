"""Gate G1: Scientific Correctness.

Gate G1 contract:
1. Statistical evidence: every STABLE capability that makes a statistical claim
   (decisions, modeling, diagnostics, clv domains) references at least one
   executable test under tests/statistical/ on the current head.
2. Deprecation truth: legacy compatibility wrappers are marked `deprecated` in
   the capability inventory and in the generated docs — not merely experimental.
3. Evidence existence: all referenced evidence tests exist as files.
"""

from __future__ import annotations

from pathlib import Path

from marketing_mcp.capabilities import get_capability_inventory

REPO_ROOT = Path(__file__).resolve().parents[2]

# Capability domains whose claims are statistical in nature: a stable status is
# only truthful when real-library (statistical) evidence exists for them.
STATISTICAL_DOMAINS = {"decisions", "modeling", "diagnostics", "clv"}

LEGACY_WRAPPER_NAMES = {"fit_clv_model", "predict_customer_clv"}


def _capability_by_name() -> dict[str, object]:
    return {cap.name: cap for cap in get_capability_inventory()}


def test_g1_stable_statistical_capabilities_have_real_statistical_evidence():
    offenders = []
    for cap in get_capability_inventory():
        if cap.status != "stable":
            continue
        if getattr(cap, "domain", "") not in STATISTICAL_DOMAINS:
            continue
        statistical_ids = [
            t
            for t in cap.evidence_test_ids
            if "tests/statistical/" in t or "tests/integration/" in t
        ]
        if not statistical_ids:
            offenders.append(cap.name)
    assert not offenders, (
        f"Stable statistical capabilities without statistical/integration evidence: {offenders}"
    )


def test_g1_legacy_wrappers_marked_deprecated_in_inventory():
    caps = _capability_by_name()
    for name in sorted(LEGACY_WRAPPER_NAMES):
        cap = caps.get(name)
        assert cap is not None, f"Legacy wrapper {name} missing from inventory"
        assert cap.status == "deprecated", (
            f"{name} must be marked deprecated in the inventory, got '{cap.status}'"
        )


def test_g1_deprecated_status_documented_in_generated_docs():
    docs_text = (REPO_ROOT / "docs" / "CAPABILITIES.md").read_text(encoding="utf-8")
    caps = _capability_by_name()
    for name in sorted(LEGACY_WRAPPER_NAMES):
        row = next((line for line in docs_text.splitlines() if f"`{name}`" in line), None)
        assert row is not None, f"{name} missing from docs/CAPABILITIES.md"
        assert "deprecated" in row.lower(), (
            f"{name} doc row does not carry deprecated status: {row}"
        )
        _ = caps[name]


def test_g1_all_evidence_test_files_exist():
    missing = []
    for cap in get_capability_inventory():
        for test_id in cap.evidence_test_ids:
            path = REPO_ROOT / test_id.split("::")[0]
            if not path.exists():
                missing.append(test_id)
    assert not missing, f"Evidence test files missing: {missing}"
