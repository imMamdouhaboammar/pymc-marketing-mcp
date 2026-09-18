"""Domain contracts for Portfolio Entity Graph and Effect Taxonomy (T9)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from marketing_mcp.errors import DomainError

PortfolioEntityType = Literal["brand", "sub_brand", "business_unit", "geography"]
PortfolioEffectType = Literal[
    "direct_channel",
    "cross_channel_spillover",
    "halo_umbrella",
    "cannibalization",
]


class PortfolioEntity(BaseModel):
    """An organizational or product entity within the multi-brand portfolio."""

    entity_id: str = Field(description="Unique entity identifier, e.g. 'brand_premium', 'subbrand_lite'")
    name: str = Field(description="Display name")
    entity_type: PortfolioEntityType = Field(description="Type of portfolio entity")
    parent_entity_id: str | None = Field(
        default=None, description="Parent entity in organizational hierarchy"
    )
    model_id: str | None = Field(
        default=None, description="MMM model ID associated with this entity outcome"
    )


class PortfolioEffectEdge(BaseModel):
    """A directional marketing spillover, halo, or cannibalization relationship."""

    source_entity_id: str = Field(description="Entity investing in marketing")
    target_entity_id: str = Field(description="Entity receiving the spillover/halo/cannibalization effect")
    source_channel: str = Field(description="Channel generating the effect")
    effect_type: PortfolioEffectType = Field(description="Taxonomy classification of effect")
    coefficient: float = Field(
        description="Spillover rate (positive for halo/spillover, negative for cannibalization)"
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class PortfolioGraph(BaseModel):
    """Directed Acyclic Graph (DAG) of portfolio entities and marketing effect edges."""

    entities: dict[str, PortfolioEntity] = Field(
        default_factory=dict, description="Entities keyed by entity_id"
    )
    edges: list[PortfolioEffectEdge] = Field(
        default_factory=list, description="Collection of effect edges"
    )

    def validate_acyclic(self) -> None:
        """Verify that spillover and halo relationships do not contain circular dependencies.

        Raises DomainError('CIRCULAR_PORTFOLIO_GRAPH') if a cycle is detected.
        """
        adj: dict[str, list[str]] = {e_id: [] for e_id in self.entities}
        for edge in self.edges:
            if edge.source_entity_id not in self.entities:
                raise DomainError(
                    "UNKNOWN_PORTFOLIO_ENTITY",
                    f"Edge source entity '{edge.source_entity_id}' is not in portfolio",
                )
            if edge.target_entity_id not in self.entities:
                raise DomainError(
                    "UNKNOWN_PORTFOLIO_ENTITY",
                    f"Edge target entity '{edge.target_entity_id}' is not in portfolio",
                )
            # Direct channel effects on same entity do not count as cross-entity cycle
            if edge.source_entity_id != edge.target_entity_id:
                adj[edge.source_entity_id].append(edge.target_entity_id)

        visited: dict[str, int] = {e_id: 0 for e_id in self.entities}  # 0=unvisited, 1=visiting, 2=visited

        def dfs(u: str) -> None:
            visited[u] = 1
            for v in adj[u]:
                if visited[v] == 1:
                    raise DomainError(
                        "CIRCULAR_PORTFOLIO_GRAPH",
                        f"Circular spillover cycle detected between '{u}' and '{v}'",
                        evidence={"cycle_source": u, "cycle_target": v},
                        next_action="Re-structure portfolio edges to form a directed acyclic hierarchy",
                    )
                if visited[v] == 0:
                    dfs(v)
            visited[u] = 2

        for e_id in self.entities:
            if visited[e_id] == 0:
                dfs(e_id)

    def evaluate_portfolio_outcome(
        self,
        base_entity_outcomes: dict[str, float],
        channel_spends: dict[str, dict[str, float]],
    ) -> dict[str, Any]:
        """Compute net portfolio outcomes including direct, halo, and cannibalization effects.

        Parameters
        ----------
        base_entity_outcomes:
            Direct unadjusted outcome for each entity {entity_id: outcome}
        channel_spends:
            Spend per entity per channel {entity_id: {channel: spend}}
        """
        self.validate_acyclic()

        net_outcomes: dict[str, float] = dict(base_entity_outcomes)
        effects_detail: list[dict[str, Any]] = []

        for edge in self.edges:
            spends_for_source = channel_spends.get(edge.source_entity_id, {})
            ch_spend = spends_for_source.get(edge.source_channel, 0.0)
            if ch_spend > 0:
                delta = ch_spend * edge.coefficient
                target = edge.target_entity_id
                net_outcomes[target] = net_outcomes.get(target, 0.0) + delta
                effects_detail.append({
                    "source": edge.source_entity_id,
                    "target": target,
                    "channel": edge.source_channel,
                    "type": edge.effect_type,
                    "delta": round(delta, 2),
                })

        return {
            "net_outcomes": {k: round(v, 2) for k, v in net_outcomes.items()},
            "total_portfolio_outcome": round(sum(net_outcomes.values()), 2),
            "effects_detail": effects_detail,
        }
