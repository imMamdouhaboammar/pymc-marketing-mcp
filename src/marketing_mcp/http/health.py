"""Health and readiness probe handlers."""

from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from marketing_mcp import __version__
from marketing_mcp.accelerators import get_engine_info
from marketing_mcp.app import Application

SERVICE_NAME = "pymc-marketing-mcp"
logger = logging.getLogger(__name__)


def _dependency_check(checks: dict[str, Any], name: str, probe) -> bool:
    try:
        probe()
    except Exception:
        logger.exception("Readiness dependency failed: %s", name)
        checks[name] = {"status": "error", "code": "DEPENDENCY_UNAVAILABLE"}
        return False
    checks[name] = {"status": "ok"}
    return True


def check_readiness(app: Application) -> tuple[bool, dict[str, Any]]:
    """Probe configured backends without exposing implementation details."""
    checks: dict[str, Any] = {}
    database_ok = _dependency_check(checks, "database", app.persistence.probe)
    artifacts_ok = _dependency_check(checks, "artifact_storage", app.artifacts.probe)
    checks["interaction_engine"] = get_engine_info()
    return database_ok and artifacts_ok, checks


async def liveness_handler(_request: Request) -> JSONResponse:
    """Report process liveness independently from dependency readiness."""
    return JSONResponse(
        {
            "status": "alive",
            "service": SERVICE_NAME,
            "version": __version__,
        }
    )


def create_readiness_handler(application: Application):
    """Create the dependency-readiness endpoint."""

    async def readiness_handler(_request: Request) -> JSONResponse:
        is_ready, checks = check_readiness(application)
        return JSONResponse(
            {
                "status": "ready" if is_ready else "unready",
                "service": SERVICE_NAME,
                "version": __version__,
                "checks": checks,
            },
            status_code=200 if is_ready else 503,
        )

    return readiness_handler
