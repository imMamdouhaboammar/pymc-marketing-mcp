from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles

from marketing_mcp import __version__
from marketing_mcp.app import Application
from marketing_mcp.auth import AuthManager, MCPAuthMiddleware
from marketing_mcp.config import Settings
from marketing_mcp.http.artifacts import create_artifact_download_handler
from marketing_mcp.http.credentials import CredentialControlAPI
from marketing_mcp.http.health import create_readiness_handler, liveness_handler
from marketing_mcp.http.safety import RequestSafetyMiddleware
from marketing_mcp.mcp.context import RequestScopedContextProvider
from marketing_mcp.mcp.server import create_server

SERVICE_NAME = "pymc-marketing-mcp"


def health_payload(*, auth_enabled: bool) -> dict[str, Any]:
    """Build the health response body from the canonical runtime version."""
    return {
        "status": "healthy",
        "service": SERVICE_NAME,
        "version": __version__,
        "transport": "streamable-http",
        "auth_enabled": auth_enabled,
        "endpoints": {
            "mcp": "/mcp",
            "health": "/health",
        },
    }


def _dashboard_dist() -> Path:
    dist_path = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"
    if not dist_path.exists():
        dist_path = Path("/app/dashboard/dist")
    return dist_path


def create_http_app(
    host: str = "127.0.0.1",
    api_key: str | None = None,
    application: Application | None = None,
    auth_manager: AuthManager | None = None,
    context_provider: Any = None,
    settings: Settings | None = None,
):
    actual_settings = settings or Settings.from_env()
    app_instance = application or Application(actual_settings)
    auth_mgr = auth_manager or AuthManager.from_settings(actual_settings)
    if auth_mgr.credential_service is None and hasattr(app_instance, "credentials"):
        auth_mgr.credential_service = app_instance.credentials
        auth_mgr.api_key_validator.credential_service = app_instance.credentials

    if api_key:
        auth_mgr.api_key_validator.add_key(api_key)
        auth_mgr.enabled = True

    if context_provider is not None:
        ctx_provider = context_provider
    elif not auth_mgr.enabled:
        from marketing_mcp.mcp.context import stdio_context_provider

        ctx_provider = stdio_context_provider
    else:
        ctx_provider = RequestScopedContextProvider()

    mcp = create_server(app_instance, context_provider=ctx_provider)
    app = mcp.streamable_http_app(host=host)

    app.add_middleware(RequestSafetyMiddleware)
    app.add_middleware(MCPAuthMiddleware, auth_manager=auth_mgr)

    async def health_check(_request):
        return JSONResponse(health_payload(auth_enabled=auth_mgr.enabled))

    dist_path = _dashboard_dist()
    index_file = dist_path / "index.html"

    async def root_handler(request):
        accept = request.headers.get("accept", "")
        if "text/html" in accept and index_file.exists():
            return HTMLResponse(index_file.read_text(encoding="utf-8"))
        return await health_check(request)

    app.add_route("/health", health_check, methods=["GET"])
    app.add_route("/health/live", liveness_handler, methods=["GET"])
    app.add_route("/health/ready", create_readiness_handler(app_instance), methods=["GET"])
    app.add_route(
        "/artifacts/{namespace}/{digest}/download",
        create_artifact_download_handler(app_instance),
        methods=["GET"],
    )
    app.add_route("/", root_handler, methods=["GET"])

    # Mount Control Plane credential management routes
    control_api = CredentialControlAPI(app_instance.credentials)
    for route in control_api.routes():
        app.routes.append(route)

    if dist_path.exists() and (dist_path / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")

    return app


def main():
    p = argparse.ArgumentParser(prog="marketing-mcp")
    p.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default=os.getenv("MARKETING_MCP_TRANSPORT", "stdio"),
    )
    p.add_argument(
        "--host",
        default=os.getenv("HOST", os.getenv("MARKETING_MCP_HOST", "0.0.0.0")),
    )
    p.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", os.getenv("MARKETING_MCP_PORT", "8080"))),
    )
    p.add_argument(
        "--api-key",
        default=os.getenv("MARKETING_MCP_API_KEY", None),
        help="Optional API key to secure the MCP server",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args()

    if args.transport == "stdio":
        create_server().run("stdio")
        return

    # Fail closed BEFORE Uvicorn starts: validate the security posture of the
    # HTTP deployment against its profile.
    from marketing_mcp.errors import DomainError

    try:
        settings = Settings.from_env()
        settings.security_profile.validate_http_posture(
            host=args.host,
            auth_enabled=bool(args.api_key) or settings.auth_enabled,
        )
        app = create_http_app(host=args.host, api_key=args.api_key, settings=settings)
    except DomainError as exc:
        import sys

        print(f"refusing to start: {exc.message}", file=sys.stderr)
        raise SystemExit(2) from exc

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
