"""Domain contracts for Portfolio Entity Graph and Effect Taxonomy (T9)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from marketing_mcp.errors import DomainError

PortfolioEntityType = Literal["brand", "sub_brand", "business_unit", "geography"]
PortfolioEffectType = Literal[
    "direct_channel",
    "cross_channel_spillover",
    "halo_umbrella",
    "cannibalization",
]

PortfolioCoefficientProvenance = Literal[
    "caller_supplied_assumption",
    "econometric_benchmark",
    "experimental_lift",
]

PortfolioConfidenceProvenance = Literal[
    "caller_specified",
    "empirical_precision",
    "unspecified",
]


class PortfolioEntity(BaseModel):
    """An organizational or product entity within the multi-brand portfolio."""

    entity_id: str = Field(
        description="Unique entity identifier, e.g. 'brand_premium', 'subbrand_lite'"
    )
    name: str = Field(description="Display name")
    entity_type: PortfolioEntityType = Field(description="Type of portfolio entity")
    parent_entity_id: str | None = Field(
        default=None, description="Parent entity in organizational hierarchy"
    )
    model_id: str | None = Field(
        default=None, description="MMM model ID associated with this entity outcome"
    )


class PortfolioEffectEdge(BaseModel):
    """A directional marketing spillover, halo, or cannibalization relationship.

    Design & Provenance Invariants:
    - coefficient_provenance explicitly records whether the edge multiplier is an
      assumed heuristic, econometric benchmark, or empirical experiment.
    - confidence defaults to None (uncalibrated) with confidence_provenance='unspecified'.
      Never fabricates an arbitrary confidence default (e.g. 0.8).
    - If effect_type == 'direct_channel', source_entity_id must equal target_entity_id.
    - If effect_type in ('halo_umbrella', 'cannibalization', 'cross_channel_spillover'),
      source_entity_id must not equal target_entity_id.
    """

    source_entity_id: str = Field(description="Entity investing in marketing")
    target_entity_id: str = Field(
        description="Entity receiving the spillover/halo/cannibalization effect"
    )
    source_channel: str = Field(description="Channel generating the effect")
    effect_type: PortfolioEffectType = Field(description="Taxonomy classification of effect")
    coefficient: float = Field(
        description="Spillover rate (positive for halo/spillover, negative for cannibalization)"
    )
    coefficient_provenance: PortfolioCoefficientProvenance = Field(
        default="caller_supplied_assumption",
        description="Origin of the effect coefficient",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Caller-provided or empirically derived confidence score (None = uncalibrated)",
    )
    confidence_provenance: PortfolioConfidenceProvenance = Field(
        default="unspecified",
        description="Provenance of the confidence score",
    )

    @model_validator(mode="after")
    def _validate_edge_semantics(self) -> "PortfolioEffectEdge":
        if self.effect_type == "direct_channel":
            if self.source_entity_id != self.target_entity_id:
                raise ValueError(
                    f"direct_channel effect requires source_entity_id == target_entity_id, "
                    f"got source='{self.source_entity_id}' and target='{self.target_entity_id}'"
                )
        else:
            if self.source_entity_id == self.target_entity_id:
                raise ValueError(
                    f"Cross-entity effect '{self.effect_type}' requires source_entity_id must not equal target_entity_id, "
                    f"got identical entity '{self.source_entity_id}'"
                )
        if self.confidence is None and self.confidence_provenance != "unspecified":
            raise ValueError(
                f"confidence_provenance must be 'unspecified' when confidence is None, "
                f"got '{self.confidence_provenance}'"
            )
        if self.confidence is not None and self.confidence_provenance == "unspecified":
            self.confidence_provenance = "caller_specified"
        return self


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

        visited: dict[str, int] = {
            e_id: 0 for e_id in self.entities
        }  # 0=unvisited, 1=visiting, 2=visited

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
                effects_detail.append(
                    {
                        "source": edge.source_entity_id,
                        "target": target,
                        "channel": edge.source_channel,
                        "type": edge.effect_type,
                        "delta": round(delta, 2),
                        "coefficient_provenance": edge.coefficient_provenance,
                    }
                )

        return {
            "net_outcomes": {k: round(v, 2) for k, v in net_outcomes.items()},
            "total_portfolio_outcome": round(sum(net_outcomes.values()), 2),
            "effects_detail": effects_detail,
            "method": "deterministic_spillover_arithmetic",
            "uncertainty_quantified": False,
            "estimation_type": "deterministic_domain_graph",
        }


#: Honest scientific alias distinguishing deterministic domain DAG from Bayesian estimation
DeterministicPortfolioGraph = PortfolioGraph
