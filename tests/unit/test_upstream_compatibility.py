"""Static checks for the declared PyMC-Marketing compatibility boundary."""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
CANARY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "upstream-canary.yml"


def _pymc_marketing_requirement() -> str:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    return next(
        dependency
        for dependency in project["dependencies"]
        if dependency.startswith("pymc-marketing")
    )


def test_supported_pymc_marketing_major_is_bounded() -> None:
    requirement = _pymc_marketing_requirement()

    assert requirement == "pymc-marketing>=1.0.0,<2"


def test_canary_separates_supported_and_future_major_semantics() -> None:
    workflow = CANARY_WORKFLOW.read_text(encoding="utf-8")
    supported_lane = workflow.split("  latest-allowed-lane:", 1)[1].split(
        "  future-major-lane:", 1
    )[0]
    future_major_lane = workflow.split("  future-major-lane:", 1)[1]

    assert "uv sync --upgrade --extra dev" in supported_lane
    assert "continue-on-error: true" not in supported_lane
    assert '"pymc-marketing>=2,<3"' not in supported_lane

    assert "continue-on-error: true" in future_major_lane
    assert 'uv pip install --upgrade --prerelease=allow "pymc-marketing>=2,<3"' in future_major_lane
    assert "scripts/compatibility_canary.py" in future_major_lane
