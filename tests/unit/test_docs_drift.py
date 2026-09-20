"""Documentation drift checks.

Task 4 contract: documentation may not claim a version, tool name, transform name, transport, or
decision-gate policy that the code does not implement. Each check has a failing fixture below.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from marketing_mcp import __version__
from marketing_mcp.docs_drift import (
    DOCUMENTED_DOCS,
    check_decision_gate_claims,
    check_dependency_ranges,
    check_docs,
    check_resource_contracts,
    check_tool_names,
    check_transform_vocabulary,
    check_transport_names,
    check_version_references,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "scripts" / "check_docs_drift.py"


# --- version references -----------------------------------------------------------------------


def test_version_drift_is_detected():
    findings = check_version_references(
        "# MCP Tool Contracts (v0.1.0)\n", path="docs/FAKE.md", canonical_version=__version__
    )
    assert findings
    assert findings[0].check == "version-reference"
    assert "0.1.0" in findings[0].message


def test_canonical_version_reference_is_accepted():
    text = f"# MCP Tool Contracts (v{__version__})\n"
    assert check_version_references(text, path="docs/FAKE.md", canonical_version=__version__) == []


def test_explicitly_historical_version_reference_is_accepted():
    text = "## Version 0.3.0 highlights (historical)\n"
    assert check_version_references(text, path="docs/FAKE.md", canonical_version=__version__) == []


def test_dependency_version_reference_is_not_treated_as_a_release_claim():
    text = "Requires `pymc-marketing>=1.0.0` and Python 3.12.13.\n"
    assert check_version_references(text, path="docs/FAKE.md", canonical_version=__version__) == []


# --- tool names -------------------------------------------------------------------------------


def test_documented_tool_that_does_not_exist_is_detected():
    findings = check_tool_names("### `forecast_revenue(model_id: str)`\n", path="docs/FAKE.md")
    assert findings
    assert findings[0].check == "tool-name"
    assert "forecast_revenue" in findings[0].message


def test_documented_real_tool_is_accepted():
    assert check_tool_names("### `fit_mmm(config: FitMMMInput)`\n", path="docs/FAKE.md") == []


# --- transform vocabulary ---------------------------------------------------------------------


def test_transform_vocabulary_drift_is_detected():
    findings = check_transform_vocabulary(
        "  - Adstocks: `geometric` (default), `exponential`.\n", path="docs/FAKE.md"
    )
    assert findings
    assert findings[0].check == "transform-vocabulary"
    assert "exponential" in findings[0].message or "geometric" in findings[0].message


def test_missing_documented_transform_is_detected():
    findings = check_transform_vocabulary(
        "  - Saturations: `logistic` (default).\n", path="docs/FAKE.md"
    )
    assert findings
    assert "undocumented" in findings[0].message.lower()


# --- transports -------------------------------------------------------------------------------


def test_documented_transport_that_does_not_exist_is_detected():
    findings = check_transport_names("uv run marketing-mcp --transport sse\n", path="docs/FAKE.md")
    assert findings
    assert findings[0].check == "transport-name"
    assert "sse" in findings[0].message


def test_documented_real_transports_are_accepted():
    text = "uv run marketing-mcp --transport stdio\nuv run marketing-mcp --transport streamable-http\n"
    assert check_transport_names(text, path="docs/FAKE.md") == []


# --- decision gate policy ---------------------------------------------------------------------


def test_decision_gate_claim_drift_is_detected():
    findings = check_decision_gate_claims(
        "<!-- drift-check: decision-gated-tools = simulate_budget -->\n", path="docs/FAKE.md"
    )
    assert findings
    assert findings[0].check == "decision-gate-claim"
    assert "optimize_budget" in findings[0].message


def test_decision_gate_claim_matching_code_is_accepted():
    marker = (
        "<!-- drift-check: decision-gated-tools = "
        "get_incremental_roas, optimize_budget, optimize_flighting, simulate_budget -->\n"
    )
    assert check_decision_gate_claims(marker, path="docs/FAKE.md") == []


def test_missing_decision_gate_marker_is_ignored_for_unrelated_docs():
    assert check_decision_gate_claims("Nothing to declare here.\n", path="docs/FAKE.md") == []


# --- resource contracts -----------------------------------------------------------------------


def test_missing_documented_resource_is_detected():
    incomplete_contract = "## MCP resources\n- `marketing://clv/{model_id}`: Stored CLV\n"
    findings = check_resource_contracts(incomplete_contract, path="docs/TOOL-CONTRACTS.md")
    assert findings
    assert any(f.check == "resource-contract" for f in findings)
    assert any("undocumented" in f.message.lower() or "missing" in f.message.lower() for f in findings)


def test_documented_resource_that_does_not_exist_is_detected():
    text = "## MCP resources\n- `marketing://nonexistent/{id}`: Fake resource\n"
    findings = check_resource_contracts(text, path="docs/TOOL-CONTRACTS.md")
    assert findings
    assert any(f.check == "resource-name" for f in findings)
    assert "marketing://nonexistent/{id}" in findings[0].message


def test_documented_real_resources_are_accepted():
    contract_text = (REPO_ROOT / "docs" / "TOOL-CONTRACTS.md").read_text(encoding="utf-8")
    assert check_resource_contracts(contract_text, path="docs/TOOL-CONTRACTS.md") == []


def test_resource_contracts_ignored_for_unrelated_docs():
    assert check_resource_contracts("- `marketing://custom`\n", path="docs/OTHER.md") == []


# --- dependency ranges ------------------------------------------------------------------------


def test_dependency_range_drift_is_detected():
    text = (
        "| Package | Declared range | Role |\n"
        "|---|---|---|\n"
        "| `pymc-marketing` | `>=1.0.0` | MMM boundary |\n"
    )
    findings = check_dependency_ranges(
        text,
        path="docs/API-COMPATIBILITY.md",
        canonical_dependencies={"pymc-marketing": ">=1.1.0,<2"},
    )
    assert findings
    assert any(f.check == "dependency-range" for f in findings)
    assert any(">=1.0.0" in f.message and ">=1.1.0,<2" in f.message for f in findings)


def test_missing_dependency_is_detected():
    text = (
        "| Package | Declared range | Role |\n"
        "|---|---|---|\n"
        "| `pydantic` | `>=2.12,<2.13` | contracts |\n"
    )
    findings = check_dependency_ranges(
        text,
        path="docs/API-COMPATIBILITY.md",
        canonical_dependencies={"pydantic": ">=2.12,<2.13", "httpx": ">=0.27,<1"},
    )
    assert findings
    assert any(f.check == "dependency-completeness" for f in findings)
    assert any("httpx" in f.message for f in findings)


def test_documented_real_dependencies_are_accepted():
    text = (REPO_ROOT / "docs" / "API-COMPATIBILITY.md").read_text(encoding="utf-8")
    assert check_dependency_ranges(text, path="docs/API-COMPATIBILITY.md") == []


def test_dependency_ranges_ignored_for_unrelated_docs():
    assert check_dependency_ranges("| `fake` | `>=1` | role |\n", path="docs/OTHER.md") == []


# --- repository-wide -------------------------------------------------------------------------


def test_documented_docs_set_is_non_empty_and_exists():
    assert DOCUMENTED_DOCS
    for relative in DOCUMENTED_DOCS:
        assert (REPO_ROOT / relative).exists(), f"{relative} is listed but missing"


def test_repository_documentation_has_no_drift():
    findings = check_docs(REPO_ROOT)
    assert findings == [], "documentation drift:\n" + "\n".join(
        f"{f.path}:{f.line} [{f.check}] {f.message}" for f in findings
    )


def test_checker_script_exits_zero_on_clean_docs():
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_checker_script_exits_non_zero_on_drift(tmp_path):
    fake_repo = tmp_path / "repo"
    (fake_repo / "docs").mkdir(parents=True)
    (fake_repo / "README.md").write_text("Release v9.9.9 is production ready.\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(fake_repo)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "9.9.9" in result.stdout + result.stderr
