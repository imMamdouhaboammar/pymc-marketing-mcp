"""Authenticated platform client for MCP server with sub-millisecond handshake (UP-061).

Connects MCP server to Axum gateway using principal tokens, propagates trace IDs,
and serves pre-cached tools/list and resources/list in <1ms to AI clients.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID, uuid4

import httpx

from marketing_mcp.capabilities import get_capability_inventory
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError


class PlatformClient:
    """Authenticated platform client connecting the Python MCP server to the Axum gateway."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.gateway_url = str(self.settings.gateway_url).rstrip("/")
        self.organization_id = self.settings.organization_id
        self.principal_id = self.settings.principal_id or str(uuid4())
        self.principal_role = self.settings.principal_role or "analyst"
        self._http_client: httpx.AsyncClient | None = None

        # Pre-cache tool and resource catalogs for <1ms handshake
        t0 = time.perf_counter()
        inventory = get_capability_inventory()
        self._cached_tools_list: list[dict[str, Any]] = [
            {
                "name": cap.name,
                "description": cap.summary,
                "domain": cap.domain,
                "status": cap.status,
                "decision_gate_required": cap.decision_gate_required,
            }
            for cap in inventory
            if cap.kind == "tool"
        ]
        self._cached_resources_list: list[dict[str, Any]] = [
            {
                "uri": cap.name,
                "name": cap.summary,
                "domain": cap.domain,
                "status": cap.status,
            }
            for cap in inventory
            if cap.kind == "resource"
        ]
        self._precache_duration_s = time.perf_counter() - t0

    def get_cached_tools_list(self) -> list[dict[str, Any]]:
        """Return pre-cached MCP tools list in < 1ms."""
        return self._cached_tools_list

    def get_cached_resources_list(self) -> list[dict[str, Any]]:
        """Return pre-cached MCP resources list in < 1ms."""
        return self._cached_resources_list

    def build_headers(self, trace_id: str | None = None) -> dict[str, str]:
        """Construct tenant-scoped HTTP headers for Axum gateway calls."""
        if not self.organization_id:
            raise DomainError(
                "AUTH_REQUIRED",
                "organization_id is required for tenant-scoped platform gateway calls",
                next_action="Set organization_id in settings or pass x-organization-id header",
            )

        return {
            "x-organization-id": str(self.organization_id),
            "x-principal-id": str(self.principal_id),
            "x-principal-role": str(self.principal_role),
            "x-trace-id": trace_id or f"trace-{uuid4().hex[:12]}",
            "accept": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.gateway_url,
                timeout=10.0,
                headers={"user-agent": "pymc-mcp-platform-client/0.1.0"},
            )
        return self._http_client

    async def check_health(self) -> dict[str, Any]:
        """Check Axum gateway readiness."""
        client = await self._get_client()
        resp = await client.get("/health/ready")
        resp.raise_for_status()
        return resp.json()

    async def list_projects(self, trace_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch tenant-scoped projects from gateway."""
        client = await self._get_client()
        headers = self.build_headers(trace_id=trace_id)
        resp = await client.get("/api/v1/projects", headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def list_datasets(self, trace_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch tenant-scoped datasets from gateway."""
        client = await self._get_client()
        headers = self.build_headers(trace_id=trace_id)
        resp = await client.get("/api/v1/datasets", headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def list_model_specs(self, trace_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch tenant-scoped model specifications from gateway."""
        client = await self._get_client()
        headers = self.build_headers(trace_id=trace_id)
        resp = await client.get("/api/v1/model-specs", headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def dispatch_run(
        self,
        model_spec_id: str | UUID,
        requested_via: str = "mcp",
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch model run through Axum gateway transactional outbox."""
        client = await self._get_client()
        headers = self.build_headers(trace_id=trace_id)
        payload = {
            "model_spec_id": str(model_spec_id),
            "requested_via": requested_via,
        }
        resp = await client.post("/api/v1/runs", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        """Close underlying HTTP client."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
