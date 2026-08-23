"""Contract tests for the HTTP health endpoint.

Slice 1.2 contract: the ``/health`` response must report ``marketing_mcp.__version__``. The HTTP
application must be constructible without starting a server so the contract is testable, and no
module under ``src/marketing_mcp`` may declare an independent release-version literal.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import marketing_mcp
from marketing_mcp.app import Application
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = REPO_ROOT / "src" / "marketing_mcp"

# Quoted release-version literals such as "0.4.0" or "v0.5.0".
RELEASE_VERSION_LITERAL = re.compile(r"""["']v?\d+\.\d+\.\d+["']""")


def _call_asgi(app: Any, path: str) -> tuple[int, dict[str, str], bytes]:
    """Drive an ASGI app for a single GET request without binding a socket."""

    async def _run() -> tuple[int, dict[str, str], bytes]:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [(b"host", b"127.0.0.1")],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8080),
        }
        sent: list[dict[str, Any]] = []

        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        await app(scope, receive, send)

        start = next(m for m in sent if m["type"] == "http.response.start")
        body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
        headers = {k.decode().lower(): v.decode() for k, v in start.get("headers", [])}
        return start["status"], headers, body

    return asyncio.run(_run())


def _http_app(tmp_path: Path, **kwargs: Any) -> Any:
    application = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    return create_http_app(host="127.0.0.1", application=application, **kwargs)


def test_health_endpoint_reports_canonical_runtime_version(tmp_path):
    status, _headers, body = _call_asgi(_http_app(tmp_path), "/health")
    assert status == 200
    payload = json.loads(body)
    assert payload["version"] == marketing_mcp.__version__


def test_health_endpoint_reports_service_identity(tmp_path):
    _status, _headers, body = _call_asgi(_http_app(tmp_path), "/health")
    payload = json.loads(body)
    assert payload["status"] == "healthy"
    assert payload["service"] == "pymc-marketing-mcp"
    assert payload["transport"] == "streamable-http"


def test_health_endpoint_stays_public_when_auth_is_enabled(tmp_path):
    """Health must remain reachable without credentials so probes keep working."""
    status, _headers, body = _call_asgi(_http_app(tmp_path, api_key="secret-key"), "/health")
    assert status == 200
    payload = json.loads(body)
    assert payload["auth_enabled"] is True
    assert "secret-key" not in body.decode()


def test_no_module_declares_an_independent_release_version_literal():
    offenders: list[str] = []
    for module in sorted(PACKAGE_DIR.rglob("*.py")):
        for lineno, line in enumerate(module.read_text(encoding="utf-8").splitlines(), start=1):
            if RELEASE_VERSION_LITERAL.search(line):
                offenders.append(f"{module.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "release-version literals must derive from marketing_mcp.__version__:\n"
        + "\n".join(offenders)
    )
