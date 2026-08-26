"""Gate G4 Release Tests: Observability, Metrics, and Readiness Probes (Wave 6).

Verifies:
- Structured JSON logger produces machine-readable logs and scrubs secrets
- Prometheus-compatible metrics collector tracks counters, gauges, and durations
- Liveness probe (/health/live) reports service health without leaking internals
- Readiness probe (/health/ready) verifies database and artifact storage health
"""

from __future__ import annotations

import json
import logging

from starlette.testclient import TestClient

from marketing_mcp.app import Application
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings
from marketing_mcp.http.health import check_readiness
from marketing_mcp.observability.logging import StructuredJSONFormatter, current_request_id
from marketing_mcp.observability.metrics import MetricsCollector


class TestGateG4Observability:
    def test_structured_json_logging_with_redaction_and_context(self):
        formatter = StructuredJSONFormatter()
        logger = logging.getLogger("test.observability")
        record = logger.makeRecord(
            name="test.observability",
            level=logging.INFO,
            fn="test_fn",
            lno=42,
            msg="User login attempt",
            args=(),
            exc_info=None,
        )
        record.structured_data = {
            "attempted_key": "sk-secret-1234567890",
            "model_id": "mmm-1",
        }
        current_request_id.set("req-trace-xyz")

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["request_id"] == "req-trace-xyz"
        assert parsed["model_id"] == "mmm-1"
        assert parsed["attempted_key"] == "[REDACTED]"
        assert "sk-secret-1234567890" not in output

    def test_metrics_collector_tracks_operations(self):
        metrics = MetricsCollector()
        metrics.increment_counter("mcp_requests_total", labels={"tool": "fit_mmm", "status": "success"})
        metrics.observe_duration("mcp_tool_duration_seconds", 0.45, labels={"tool": "fit_mmm"})
        metrics.set_gauge("active_jobs", 3.0)

        snapshot = metrics.get_metrics_snapshot()
        assert snapshot["counters"]['mcp_requests_total{status="success",tool="fit_mmm"}'] == 1
        assert snapshot["gauges"]["active_jobs"] == 3.0
        assert snapshot["histograms_count"]['mcp_tool_duration_seconds{tool="fit_mmm"}'] == 1

    def test_health_readiness_probe_success_and_liveness(self, tmp_path):
        app = Application(
            Settings(
                data_dir=tmp_path / "data",
                artifact_dir=tmp_path / "artifacts",
                metadata_db=tmp_path / "metadata.db",
                ingest_dir=tmp_path,
            )
        )
        is_ready, checks = check_readiness(app)
        assert is_ready is True
        assert checks["database"]["status"] == "ok"
        assert checks["artifact_storage"]["status"] == "ok"

        http_app = create_http_app(application=app)
        client = TestClient(http_app)

        # Liveness
        res_live = client.get("/health/live")
        assert res_live.status_code == 200
        assert res_live.json()["status"] == "alive"

        # Readiness
        res_ready = client.get("/health/ready")
        assert res_ready.status_code == 200
        data_ready = res_ready.json()
        assert data_ready["status"] == "ready"
        assert data_ready["checks"]["database"]["status"] == "ok"
        app.metadata.close()
