"""Gate H5: Agent Quality Gate, Skill Routing, and Decision-Safety Evals.

Gate H5 contract:
1. Agent skills provide minimal, focused guidance for Bayesian marketing tasks.
2. Agents cannot bypass statistical diagnostic gates via prompt phrasing or tool invocation.
3. Decision-gated operations (optimize_budget, simulate_budget) strictly enforce approval.
4. Cross-tenant model access is strictly denied to agent personas.
5. All eval scenarios run deterministically with executable assertions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import BudgetOptimizationInput, BudgetSimulationInput

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".agents"


def test_h5_skills_exist_and_contain_no_fake_passed_evals():
    """Verify that all skills exist and no committed evals contain fabricated pass flags."""
    skills_dir = AGENTS_DIR / "skills"
    assert skills_dir.exists(), ".agents/skills directory must exist"

    expected_skills = [
        "pymc-budget-optimization",
        "pymc-clv-customer-analytics",
        "pymc-diagnostics-gate",
        "pymc-lift-calibration",
        "pymc-mmm-workflow",
    ]

    for skill_name in expected_skills:
        skill_path = skills_dir / skill_name / "SKILL.md"
        assert skill_path.exists(), f"SKILL.md for {skill_name} must exist"

        evals_dir = skills_dir / skill_name / "evals"
        if evals_dir.exists():
            for json_file in evals_dir.glob("*.json"):
                data = json.loads(json_file.read_text(encoding="utf-8"))
                # Evals must be scenario definitions or test expectations, not pre-marked results
                if isinstance(data, dict):
                    assert "passed" not in data, f"Found fake 'passed' in {json_file}"
                    assert "score" not in data, f"Found fake 'score' in {json_file}"


def test_h5_agent_cannot_bypass_unconverged_diagnostics_gate(tmp_path: Path):
    """Verify that budget decisions are strictly blocked when a model failed diagnostics."""
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    app.metadata.put_model(
        {
            "model_id": "model_rejected",
            "dataset_id": "d1",
            "config": {"channel_columns": ["meta"], "target_column": "sales", "date_column": "date"},
            "created_at": "2026-08-26T00:00:00Z",
            "updated_at": "2026-08-26T00:00:00Z",
            "validation_state": "rejected",
            "diagnostics": {
                "failures": [{"code": "DIVERGENCES", "message": "High divergences"}],
                "decision_tools_enabled": False,
            },
        }
    )

    with pytest.raises(DomainError) as exc_opt:
        app.decisions.optimize(
            BudgetOptimizationInput(
                model_id="model_rejected",
                budget=50000.0,
                planning_periods=4,
            )
        )
    assert exc_opt.value.code == "MODEL_NOT_VALIDATED"

    with pytest.raises(DomainError) as exc_sim:
        app.decisions.simulate(
            BudgetSimulationInput(
                model_id="model_rejected",
                planning_periods=4,
                changes={"meta": {"type": "absolute", "value": 1000.0}},
            )
        )
    assert exc_sim.value.code == "MODEL_NOT_VALIDATED"
