from __future__ import annotations

import argparse
import os

from starlette.responses import JSONResponse

from marketing_mcp.mcp.server import create_server


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
    args = p.parse_args()
    mcp = create_server()
    if args.transport == "stdio":
        mcp.run("stdio")
    else:
        import uvicorn

        from marketing_mcp.auth import AuthManager, MCPAuthMiddleware

        app = mcp.streamable_http_app(host=args.host)

        # Build auth manager from args/env
        auth_mgr = AuthManager.from_env()
        if args.api_key:
            auth_mgr.api_key_validator.add_key(args.api_key)
            auth_mgr.enabled = True

        app.add_middleware(MCPAuthMiddleware, auth_manager=auth_mgr)

        async def health_check(_request):
            return JSONResponse(
                {
                    "status": "healthy",
                    "service": "pymc-marketing-mcp",
                    "version": "0.4.0",
                    "transport": "streamable-http",
                    "auth_enabled": auth_mgr.enabled,
                    "endpoints": {
                        "mcp": "/mcp",
                        "health": "/health",
                    },
                }
            )

        from pathlib import Path

        from starlette.responses import HTMLResponse
        from starlette.staticfiles import StaticFiles


        dist_path = Path(__file__).resolve().parent.parent.parent / "dashboard" / "dist"
        if not dist_path.exists():
            dist_path = Path("/app/dashboard/dist")

        index_file = dist_path / "index.html"

        async def root_handler(request):
            accept = request.headers.get("accept", "")
            if "text/html" in accept and index_file.exists():
                return HTMLResponse(index_file.read_text(encoding="utf-8"))
            return await health_check(request)

        app.add_route("/health", health_check, methods=["GET"])
        app.add_route("/", root_handler, methods=["GET"])

        if dist_path.exists() and (dist_path / "assets").exists():
            app.mount("/assets", StaticFiles(directory=str(dist_path / "assets")), name="assets")

        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()


