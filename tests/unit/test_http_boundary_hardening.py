"""Negative tests for the public HTTP boundary: credentials, auth bypass and artifact reads."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from marketing_mcp.app import Application
from marketing_mcp.auth import AuthManager, create_jwt_token
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings
from marketing_mcp.security.artifact_token import (
    generate_artifact_download_token,
    verify_artifact_download_token,
)

JWT_SECRET = "boundary-hardening-jwt-secret-0123456789abcdef"


def _application(tmp_path: Path) -> Application:
    return Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path / "inbox",
        )
    )


def _bearer(client_id: str, tenant_id: str) -> dict[str, str]:
    token = create_jwt_token(secret=JWT_SECRET, client_id=client_id, tenant_id=tenant_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def secured(tmp_path: Path):
    app_instance = _application(tmp_path)
    auth = AuthManager(
        jwt_secret=JWT_SECRET, enabled=True, credential_service=app_instance.credentials
    )
    client = TestClient(create_http_app(application=app_instance, auth_manager=auth))
    return client, app_instance


@pytest.fixture
def anonymous(tmp_path: Path):
    app_instance = _application(tmp_path)
    auth = AuthManager(enabled=False, credential_service=app_instance.credentials)
    client = TestClient(create_http_app(application=app_instance, auth_manager=auth))
    return client, app_instance


def _store_blob(app_instance: Application, owner: str, tenant_id: str):
    data = b"posterior-trace-bytes" * 64
    ref = app_instance.artifacts.put_bytes(
        data, content_type="application/octet-stream", owner=owner, tenant_id=tenant_id
    )
    namespace = app_instance.artifacts._namespace(owner, tenant_id)
    return data, ref, namespace


def test_anonymous_server_refuses_to_issue_api_keys(anonymous):
    client, app_instance = anonymous

    response = client.post("/control/credentials", json={"name": "backdoor"})

    assert response.status_code == 403
    assert "secret" not in response.json()
    assert app_instance.credentials.list_for_owner(
        tenant_id="default", owner_subject="anonymous"
    ) == []


def test_json_suffix_does_not_bypass_authentication(secured):
    client, _ = secured

    response = client.get("/control/credentials.json")

    assert response.status_code == 401


def test_unauthorized_response_does_not_advertise_query_string_credentials(secured):
    client, _ = secured

    body = client.get("/control/credentials").json()

    assert all("?token" not in scheme for scheme in body["error"]["data"]["supported_schemes"])


def test_authenticated_caller_cannot_read_another_tenants_artifact(secured):
    client, app_instance = secured
    data, ref, namespace = _store_blob(app_instance, "alice", "tenant_a")
    url = f"/artifacts/{namespace}/{ref.sha256}/download"

    intruder = client.get(url, headers=_bearer("mallory", "tenant_b"))
    owner = client.get(url, headers=_bearer("alice", "tenant_a"))

    assert intruder.status_code == 401
    assert owner.status_code == 200
    assert owner.content == data


def test_signed_link_works_without_credentials_and_only_for_its_artifact(secured):
    client, app_instance = secured
    data, ref, namespace = _store_blob(app_instance, "alice", "tenant_a")
    _, other_ref, other_namespace = _store_blob(app_instance, "bob", "tenant_b")
    token = generate_artifact_download_token(
        namespace=namespace, digest=ref.sha256, owner="alice", tenant_id="tenant_a"
    )

    allowed = client.get(f"/artifacts/{namespace}/{ref.sha256}/download?token={token}")
    reused = client.get(f"/artifacts/{other_namespace}/{other_ref.sha256}/download?token={token}")
    missing = client.get(f"/artifacts/{namespace}/{ref.sha256}/download")

    assert allowed.status_code == 200
    assert allowed.content == data
    assert reused.status_code == 401
    assert missing.status_code == 401


def test_token_signed_with_former_hardcoded_default_key_is_rejected(monkeypatch):
    monkeypatch.delenv("MARKETING_MCP_TOKEN_SECRET", raising=False)
    monkeypatch.delenv("MARKETING_MCP_API_KEY", raising=False)
    payload = json.dumps(
        {"ns": "a" * 24, "sha": "b" * 64, "own": "x", "tid": "default", "exp": int(time.time()) + 60},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    key = hashlib.sha256(b"default-ephemeral-artifact-secret").digest()
    forged = (
        base64.urlsafe_b64encode(payload).decode().rstrip("=")
        + "."
        + hmac.new(key, payload, hashlib.sha256).hexdigest()
    )

    assert not verify_artifact_download_token(
        forged, expected_namespace="a" * 24, expected_digest="b" * 64
    )


def test_download_filename_cannot_inject_header_content(anonymous):
    client, app_instance = anonymous
    _, ref, namespace = _store_blob(app_instance, "alice", "tenant_a")

    response = client.get(
        f"/artifacts/{namespace}/{ref.sha256}/download",
        params={"filename": 'x"; evil=1\r\nSet-Cookie: a=b'},
    )

    assert response.status_code == 200
    disposition = response.headers["content-disposition"]
    assert disposition.count('"') == 2
    assert "\r" not in disposition and "\n" not in disposition
    assert ";" not in disposition.split("filename=", 1)[1]
