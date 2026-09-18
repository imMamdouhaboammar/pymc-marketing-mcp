"""Unit tests for Portfolio Entity Graph and Effect Taxonomy (T9).

Fast tests — zero sampling required.
Requirements tested:
- Acyclic graph validation (passes DAGs, rejects circular cycles)
- Accurate evaluation of halo spillovers and negative cannibalization
- Multi-entity portfolio aggregation
"""

from __future__ import annotations

import pytest

from marketing_mcp.domain.portfolio import (
    PortfolioEffectEdge,
    PortfolioEntity,
    PortfolioGraph,
)
from marketing_mcp.errors import DomainError


class TestPortfolioGraph:
    def test_valid_dag_passes_validation(self):
        entities = {
            "parent_brand": PortfolioEntity(entity_id="parent_brand", name="Parent Brand", entity_type="brand"),
            "sub_brand_a": PortfolioEntity(entity_id="sub_brand_a", name="Sub Brand A", entity_type="sub_brand", parent_entity_id="parent_brand"),
            "sub_brand_b": PortfolioEntity(entity_id="sub_brand_b", name="Sub Brand B", entity_type="sub_brand", parent_entity_id="parent_brand"),
        }
        edges = [
            # Umbrella TV spend creates positive halo on sub_brand_a
            PortfolioEffectEdge(
                source_entity_id="parent_brand",
                target_entity_id="sub_brand_a",
                source_channel="tv",
                effect_type="halo_umbrella",
                coefficient=0.15,
            ),
            # Performance spend on sub_brand_a cannibalizes sub_brand_b
            PortfolioEffectEdge(
                source_entity_id="sub_brand_a",
                target_entity_id="sub_brand_b",
                source_channel="search",
                effect_type="cannibalization",
                coefficient=-0.05,
            ),
        ]
        graph = PortfolioGraph(entities=entities, edges=edges)
        graph.validate_acyclic()  # should not raise

    def test_circular_graph_fails_validation(self):
        entities = {
            "entity_1": PortfolioEntity(entity_id="entity_1", name="E1", entity_type="brand"),
            "entity_2": PortfolioEntity(entity_id="entity_2", name="E2", entity_type="brand"),
        }
        edges = [
            PortfolioEffectEdge(source_entity_id="entity_1", target_entity_id="entity_2", source_channel="tv", effect_type="cross_channel_spillover", coefficient=0.1),
            PortfolioEffectEdge(source_entity_id="entity_2", target_entity_id="entity_1", source_channel="tv", effect_type="cross_channel_spillover", coefficient=0.1),
        ]
        graph = PortfolioGraph(entities=entities, edges=edges)
        with pytest.raises(DomainError) as exc_info:
            graph.validate_acyclic()
        assert exc_info.value.code == "CIRCULAR_PORTFOLIO_GRAPH"

    def test_evaluate_portfolio_outcome_applies_halo_and_cannibalization(self):
        entities = {
            "flagship": PortfolioEntity(entity_id="flagship", name="Flagship Brand", entity_type="brand"),
            "midtier": PortfolioEntity(entity_id="midtier", name="Midtier Brand", entity_type="sub_brand"),
            "budget": PortfolioEntity(entity_id="budget", name="Budget Brand", entity_type="sub_brand"),
        }
        edges = [
            # Flagship branding creates 20% positive halo on midtier
            PortfolioEffectEdge(
                source_entity_id="flagship",
                target_entity_id="midtier",
                source_channel="tv",
                effect_type="halo_umbrella",
                coefficient=0.20,
            ),
            # Midtier discount spend cannibalizes budget by -10%
            PortfolioEffectEdge(
                source_entity_id="midtier",
                target_entity_id="budget",
                source_channel="promo",
                effect_type="cannibalization",
                coefficient=-0.10,
            ),
        ]
        graph = PortfolioGraph(entities=entities, edges=edges)

        base_outcomes = {"flagship": 100000.0, "midtier": 50000.0, "budget": 20000.0}
        spends = {
            "flagship": {"tv": 20000.0},
            "midtier": {"promo": 10000.0},
            "budget": {},
        }

        res = graph.evaluate_portfolio_outcome(base_outcomes, spends)

        # Flagship: 100,000 base = 100,000
        assert res["net_outcomes"]["flagship"] == pytest.approx(100000.0)
        # Midtier: 50,000 base + 4,000 halo (20,000 * 0.20) = 54,000
        assert res["net_outcomes"]["midtier"] == pytest.approx(54000.0)
        # Budget: 20,000 base - 1,000 cannibalization (10,000 * -0.10) = 19,000
        assert res["net_outcomes"]["budget"] == pytest.approx(19000.0)
        # Total portfolio: 100,000 + 54,000 + 19,000 = 173,000
        assert res["total_portfolio_outcome"] == pytest.approx(173000.0)
