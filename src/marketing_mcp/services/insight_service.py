"""Agent Insights and interaction logging service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from marketing_mcp.repositories.base import MetadataRepository
from marketing_mcp.schemas.models import QueryInsightsInput, RecordInsightInput
from marketing_mcp.security.principal import Principal


class InsightService:
    """Provides structured storage and retrieval for AI client interaction logs and insights."""

    def __init__(self, metadata: MetadataRepository):
        self.metadata = metadata

    def record_insight(
        self, input_data: RecordInsightInput, principal: Principal | None = None
    ) -> dict[str, Any]:
        tenant_id = principal.tenant_id if principal and principal.tenant_id else "default"
        agent_id = (
            input_data.agent_id
            or (principal.subject if principal and principal.subject else "coding-agent")
        )
        now = datetime.now(UTC).isoformat()
        insight_id = f"ins_{uuid.uuid4().hex[:12]}"

        payload = {
            "insight_id": insight_id,
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "category": input_data.category,
            "severity": input_data.severity,
            "summary": input_data.summary,
            "details": input_data.details,
            "model_id": input_data.model_id,
            "dataset_id": input_data.dataset_id,
            "tags": input_data.tags,
            "created_at": now,
        }

        self.metadata.put_insight(payload)
        return payload

    def list_insights(
        self, query: QueryInsightsInput | None = None, principal: Principal | None = None
    ) -> list[dict[str, Any]]:
        tenant_id = principal.tenant_id if principal and principal.tenant_id else "default"
        q = query or QueryInsightsInput()
        return self.metadata.list_insights(
            tenant_id=tenant_id,
            model_id=q.model_id,
            dataset_id=q.dataset_id,
            category=q.category,
            tag=q.tag,
            limit=q.limit,
        )

    def get_insight(self, insight_id: str, principal: Principal | None = None) -> dict[str, Any]:
        tenant_id = principal.tenant_id if principal and principal.tenant_id else "default"
        return self.metadata.get_insight(tenant_id, insight_id)
