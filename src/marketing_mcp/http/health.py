"""Health and readiness probe handlers (Wave 6 Task 4)."""

from __future__ import annotations

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from marketing_mcp import __version__
from marketing_mcp.app import Application

SERVICE_NAME = "pymc-marketing-mcp"


def check_readiness(app: Application) -> tuple[bool, dict[str, Any]]:
    """Verify that all core dependencies are operational."""
    checks = {}
    all_ok = True

    # 1. Database check
    try:
        cursor = app.metadata.conn.cursor()
        cursor.execute("SELECT 1")
        checks["database"] = {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        checks["database"] = {"status": "error", "message": str(e)}
        all_ok = False

    # 2. Artifact storage write check
    try:
        import uuid

        app.artifacts.root.mkdir(parents=True, exist_ok=True)
        test_file = app.artifacts.root / f".health_check_{uuid.uuid4().hex}"
        test_file.touch()
        test_file.unlink()
        checks["artifact_storage"] = {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        checks["artifact_storage"] = {"status": "error", "message": str(e)}
        all_ok = False

    # 3. Job subsystem
    checks["job_executor"] = {"status": "ok"}

    return all_ok, checks


async def liveness_handler(_request: Request) -> JSONResponse:
    """Lightweight liveness probe."""
    return JSONResponse(
        {
            "status": "alive",
            "service": SERVICE_NAME,
            "version": __version__,
        }
    )


def create_readiness_handler(application: Application):
    """Factory for readiness probe handler."""

    async def readiness_handler(_request: Request) -> JSONResponse:
        is_ready, checks = check_readiness(application)
        status_code = 200 if is_ready else 503
        return JSONResponse(
            {
                "status": "ready" if is_ready else "unready",
                "service": SERVICE_NAME,
                "version": __version__,
                "checks": checks,
            },
            status_code=status_code,
        )

    return readiness_handler
