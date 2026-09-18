"""Tests for unified MarketingDataIntelligenceEngine."""

from __future__ import annotations

import pandas as pd

from marketing_mcp.intelligence.contracts.suitability import AnalysisType, SuitabilityVerdict


def test_engine_end_to_end_clean_mmm():
    from marketing_mcp.intelligence.engine import MarketingDataIntelligenceEngine

    dates = pd.date_range("2025-01-06", periods=60, freq="W-MON")
    df = pd.DataFrame({
        "date": dates,
        "revenue_usd": [10000.0 + i * 150 for i in range(60)],
        "google_spend": [1200.0 + (i % 4) * 100 for i in range(60)],
        "meta_spend": [800.0 + (i % 3) * 80 for i in range(60)],
    })

    engine = MarketingDataIntelligenceEngine()
    contract = engine.analyze_dataset(df, dataset_id="clean_mmm_test")

    assert contract.dataset_id == "clean_mmm_test"
    assert contract.structural.rows == 60
    assert contract.structural.columns == 4
    assert contract.structural.temporal.frequency == "weekly"
    assert contract.target is not None
    assert contract.target.column == "revenue_usd"
    assert len(contract.channels) == 2
    assert {c.column for c in contract.channels} == {"google_spend", "meta_spend"}

    mmm_assessment = contract.suitability[AnalysisType.MMM]
    assert mmm_assessment.verdict in (SuitabilityVerdict.SUITABLE, SuitabilityVerdict.SUITABLE_WITH_CAUTION)
    assert contract.modeling_contract is not None
    assert contract.modeling_contract.date_column == "date"
    assert contract.modeling_contract.target_column == "revenue_usd"


def test_engine_clarification_on_ambiguous_targets():
    from marketing_mcp.intelligence.engine import MarketingDataIntelligenceEngine

    # Two plausible independent revenue targets
    dates = pd.date_range("2025-01-06", periods=60, freq="W-MON")
    df = pd.DataFrame({
        "date": dates,
        "ecommerce_revenue": [10000.0 + i * 100 for i in range(60)],
        "crm_gross_revenue": [12000.0 + i * 110 for i in range(60)],
        "google_spend": [1000.0] * 60,
    })

    engine = MarketingDataIntelligenceEngine()
    contract = engine.analyze_dataset(df, dataset_id="ambiguous_target_test")

    assert len(contract.clarification_requests) >= 1
    assert any("target" in q.question.lower() or "revenue" in q.question.lower() for q in contract.clarification_requests)
