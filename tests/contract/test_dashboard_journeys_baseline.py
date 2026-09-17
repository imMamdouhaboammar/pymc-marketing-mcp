"""Contract tests verifying Dashboard critical journeys baseline characterization (UP-007)."""

from __future__ import annotations

import json
from pathlib import Path

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines"


def test_dashboard_critical_journeys_structure():
    with open(BASELINES_DIR / "dashboard_critical_journeys.json", encoding="utf-8") as f:
        data = json.load(f)

    assert data["schema_version"] == "1.0"
    journeys = {j["id"]: j for j in data["journeys"]}

    assert "J1_DATA_UPLOAD" in journeys
    assert "J2_ANALYZE_STREAM" in journeys
    assert "J3_CANCEL_EXECUTION" in journeys
    assert "J4_CLEAR_SESSION" in journeys

    # Verify upload contract
    j1 = journeys["J1_DATA_UPLOAD"]
    assert j1["endpoint"] == "/api/upload"
    assert j1["method"] == "POST"
    assert "file" in j1["required_fields"]
    assert j1["response_schema"]["type"] == "object"
    assert set(j1["response_schema"]["required"]) == {"name", "content", "size"}

    # Verify analyze contract
    j2 = journeys["J2_ANALYZE_STREAM"]
    assert j2["endpoint"] == "/api/analyze"
    assert j2["expected_content_type"] == "text/event-stream"
    assert "question" in j2["required_fields"]

    # Verify cancel contract
    j3 = journeys["J3_CANCEL_EXECUTION"]
    assert j3["endpoint"] == "/api/cancel-show"
    assert "generationId" in j3["required_fields"]
