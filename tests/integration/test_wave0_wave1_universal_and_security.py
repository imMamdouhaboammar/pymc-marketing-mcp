import pytest
from starlette.testclient import TestClient

from marketing_mcp.app import Application
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError


def test_universal_agent_discovery_endpoint(tmp_path):
    """Wave 0: Remote agents (ChatGPT, Codex, Gemini, Claude) need clear discovery and health info."""
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path,
        auth_enabled=False,
    )
    app = create_http_app(host="127.0.0.1", settings=settings)
    client = TestClient(app)

    # 1. Health endpoint returns all endpoints and discovery metadata
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "endpoints" in data
    assert data["endpoints"]["mcp"] == "/mcp"

    # 2. Well-known discovery endpoint for AI Agents / Connectors
    well_known_resp = client.get("/.well-known/mcp.json")
    assert well_known_resp.status_code == 200
    well_known = well_known_resp.json()
    assert well_known["name"] == "PyMC Marketing MCP"
    assert "mcp_endpoint" in well_known


def test_export_artifact_never_leaks_server_api_key(tmp_path, monkeypatch):
    """Wave 1: P0 Security - export_artifact_to_sandbox must NEVER expose MARKETING_MCP_API_KEY."""
    secret_key = "sk-super-secret-server-master-key-xyz"
    monkeypatch.setenv("MARKETING_MCP_API_KEY", secret_key)
    monkeypatch.setenv("MARKETING_MCP_PUBLIC_BASE_URL", "http://127.0.0.1:8080")

    app_instance = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )

    # Create dummy artifact using canonical put_bytes
    test_bytes = b"fake-netcdf-model-data"
    ref = app_instance.artifacts.put_bytes(
        test_bytes,
        content_type="application/octet-stream",
        owner="alice",
        tenant_id="tenant-1",
    )

    # Call export_to_sandbox
    result = app_instance.artifacts.export_to_sandbox(
        ref,
        owner="alice",
        tenant_id="tenant-1",
        export_name="model.nc",
        base_url="http://127.0.0.1:8080",
        api_key=secret_key,
    )

    # Invariant: Secret key MUST NOT be present anywhere in the result
    result_str = str(result)
    assert secret_key not in result_str, "CRITICAL: Server API Key leaked into export payload!"
    assert "Authorization: Bearer sk-super-secret" not in result["sandbox_curl_command"]
    assert "Authorization: Bearer sk-super-secret" not in result["python_snippet"]
    
    # Must provide scoped download token or signed URL
    assert "download_url" in result
    assert "download_token" in result or "is_signed_url" in result


def test_safe_fetch_remote_dataset_rejects_ssrf(tmp_path):
    """Wave 1: P0 Security - Remote dataset download must reject private, loopback, and metadata IPs."""
    from marketing_mcp.security.remote_fetch import safe_fetch_remote_dataset

    # 1. Reject localhost / loopback
    with pytest.raises(DomainError) as exc_info:
        safe_fetch_remote_dataset("http://127.0.0.1/data.csv", max_bytes=1024)
    assert exc_info.value.code in ("SSRF_DETECTED", "BLOCKED_DESTINATION")

    # 2. Reject metadata endpoint
    with pytest.raises(DomainError) as exc_info:
        safe_fetch_remote_dataset("http://169.254.169.254/latest/meta-data/", max_bytes=1024)
    assert exc_info.value.code in ("SSRF_DETECTED", "BLOCKED_DESTINATION")

    # 3. Reject RFC1918 internal networks
    for private_ip in ["10.0.0.1", "172.16.0.1", "192.168.1.1"]:
        with pytest.raises(DomainError) as exc_info:
            safe_fetch_remote_dataset(f"http://{private_ip}/sales.csv", max_bytes=1024)
        assert exc_info.value.code in ("SSRF_DETECTED", "BLOCKED_DESTINATION")
