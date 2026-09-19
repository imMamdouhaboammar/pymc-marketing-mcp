"""Unified Marketing Data Intelligence Engine orchestrator."""

from __future__ import annotations

from typing import Any

import pandas as pd

from marketing_mcp.intelligence.contracts.contract import (
    ClarificationRequest,
    ModelingContract,
    SemanticDatasetContract,
)
from marketing_mcp.intelligence.contracts.issues import (
    IntelligenceIssue,
    IssueCode,
    IssueSeverity,
)
from marketing_mcp.intelligence.contracts.semantics import InferredColumn, SemanticRole
from marketing_mcp.intelligence.contracts.suitability import (
    AnalysisType,
    SuitabilityAssessment,
)
from marketing_mcp.intelligence.marketing.lifecycle import analyze_channel_lifecycles
from marketing_mcp.intelligence.marketing.market_structure import analyze_market_structure
from marketing_mcp.intelligence.marketing.tracking_quality import analyze_tracking_quality
from marketing_mcp.intelligence.semantics.currencies import infer_currencies
from marketing_mcp.intelligence.semantics.objectives import analyze_campaign_objectives
from marketing_mcp.intelligence.semantics.roles import infer_all_column_roles
from marketing_mcp.intelligence.statistical.break_detection import detect_structural_breaks
from marketing_mcp.intelligence.statistical.collinearity import assess_collinearity
from marketing_mcp.intelligence.statistical.control_variance import assess_control_variance
from marketing_mcp.intelligence.statistical.identifiability import evaluate_identifiability_risk
from marketing_mcp.intelligence.statistical.target_leakage import check_target_leakage
from marketing_mcp.intelligence.statistical.variance import assess_spend_variance
from marketing_mcp.intelligence.structural.profiler import profile_structure
from marketing_mcp.intelligence.suitability.clv import evaluate_clv_suitability
from marketing_mcp.intelligence.suitability.mmm import evaluate_mmm_suitability
from marketing_mcp.intelligence.suitability.panel_mmm import evaluate_panel_mmm_suitability
from marketing_mcp.intelligence.transformations.planner import build_transformation_plan


class MarketingDataIntelligenceEngine:
    """Authoritative pre-modeling intelligence engine for marketing science data."""

    def analyze_dataset(
        self,
        df: pd.DataFrame,
        dataset_id: str = "ad_hoc",
        user_overrides: dict[str, Any] | None = None,
        analysis_type: str = "mmm",
        dims: list[str] | None = None,
    ) -> SemanticDatasetContract:
        """Runs comprehensive structural, semantic, statistical, and suitability profiling."""
        from marketing_mcp.schemas.overrides import normalize_user_overrides
        user_overrides = normalize_user_overrides(user_overrides)
        override_dims = [
            col
            for col, spec in user_overrides.items()
            if isinstance(spec, dict) and spec.get("role") == SemanticRole.DIMENSION
        ]
        dims = list(dict.fromkeys([*(dims or []), *override_dims]))

        # 1. Structural profiling
        date_override = next((col for col, ov in user_overrides.items() if isinstance(ov, dict) and ov.get("role") == SemanticRole.DATE), None)
        structural = profile_structure(df, date_column=date_override)

        # 2. Semantic role inference
        columns = infer_all_column_roles(df, structural, user_overrides=user_overrides)

        # Classify columns by role
        target_col: InferredColumn | None = None
        target_candidates: list[InferredColumn] = []
        channels: list[InferredColumn] = []
        controls: list[InferredColumn] = []
        dimensions: list[InferredColumn] = []

        for col_name, inf in columns.items():
            if inf.role == SemanticRole.TARGET:
                target_candidates.append(inf)
            elif inf.role == SemanticRole.MEDIA_CHANNEL:
                channels.append(inf)
            elif inf.role == SemanticRole.CONTROL:
                controls.append(inf)
            elif inf.role == SemanticRole.DIMENSION:
                dimensions.append(inf)

        # Ambiguous target handling
        clarifications: list[ClarificationRequest] = []
        issues: list[IntelligenceIssue] = []

        # Select primary target
        if len(target_candidates) == 1:
            target_col = target_candidates[0]
        elif len(target_candidates) > 1:
            # Check if one was user overridden
            overridden = [t for t in target_candidates if t.user_overridden]
            if overridden:
                target_col = overridden[0]
            else:
                # Prefer non-attributed target first, then highest confidence
                non_attr = [
                    t for t in target_candidates
                    if not any("attributed" in s.signal_name.lower() for s in t.confidence.evidence)
                ]
                candidates_to_rank = non_attr if non_attr else target_candidates
                target_col = max(candidates_to_rank, key=lambda t: t.confidence.score)

                # Surface clarification request
                clarifications.append(
                    ClarificationRequest(
                        question=f"Multiple plausible revenue/conversion targets detected ({[t.column for t in target_candidates]}). Which represents primary business outcome?",
                        context="Using platform-attributed vs CRM revenue fundamentally changes causal interpretation.",
                        options=[t.column for t in target_candidates],
                        affected_analysis="mmm",
                    )
                )
                issues.append(
                    IntelligenceIssue(
                        code=IssueCode.AMBIGUOUS_TARGET,
                        severity=IssueSeverity.WARNING,
                        summary=f"Multiple candidate targets detected ({[t.column for t in target_candidates]}). Auto-selected '{target_col.column}'.",
                        evidence={"candidates": [t.column for t in target_candidates], "selected": target_col.column},
                        affected_columns=[t.column for t in target_candidates],
                        why_it_matters="Selecting the wrong target confounds paid media contribution with baseline or attribution artifacts",
                        recommended_action="Explicitly specify target_column in user overrides",
                        blocking=False,
                    )
                )

        # 3. Currency detection
        currencies = infer_currencies(df)

        # 4. Campaign objective analysis
        obj_report = analyze_campaign_objectives(df)
        if obj_report.issue:
            issues.append(obj_report.issue)

        # 5. Channel lifecycle analysis
        channel_names = [c.column for c in channels]
        date_col_name = structural.temporal.date_column or "date"
        lifecycle_report = analyze_channel_lifecycles(df, date_col_name, channel_names)
        issues.extend(lifecycle_report.issues)

        # 6. Market structure analysis
        market_report = analyze_market_structure(df, date_col_name, dims=dims)
        if market_report.issue:
            issues.append(market_report.issue)

        # 7. Tracking quality analysis
        target_name = target_col.column if target_col else ""
        tracking_report = analyze_tracking_quality(df, target_name, channel_names)
        if tracking_report.issue:
            issues.append(tracking_report.issue)

        # 8. Statistical suitability: variance, collinearity, leakage, breaks, controls
        var_report = assess_spend_variance(df, channel_names)
        issues.extend(var_report.issues)

        coll_report = assess_collinearity(df, channel_names)
        issues.extend(coll_report.issues)

        control_names = [c.column for c in controls]
        if target_col:
            leakage_issues = check_target_leakage(
                df,
                target_column=target_col.column,
                candidate_controls=control_names,
                candidate_channels=channel_names,
            )
            issues.extend(leakage_issues)

            break_issues = detect_structural_breaks(
                df,
                date_column=date_col_name,
                target_column=target_col.column,
            )
            issues.extend(break_issues)

        if control_names:
            control_var_issues = assess_control_variance(df, control_names)
            issues.extend(control_var_issues)

        # 9. Identifiability risk synthesis
        issue_codes = [iss.code for iss in issues]
        ident_risk = evaluate_identifiability_risk(
            temporal=structural.temporal,
            collinearity_issues=[c for c in issue_codes if c == IssueCode.HIGH_CHANNEL_COLLINEARITY],
            variance_issues=[c for c in issue_codes if c == IssueCode.LOW_VARIATION_CHANNEL],
            staggered_issues=[c for c in issue_codes if c == IssueCode.STAGGERED_CHANNEL_LIFECYCLE],
            sparse_issues=[c for c in issue_codes if c == IssueCode.SPARSE_CHANNEL],
            leakage_issues=[c for c in issue_codes if c == IssueCode.TARGET_LEAKAGE],
            break_issues=[c for c in issue_codes if c == IssueCode.STRUCTURAL_BREAK],
        )

        # Deduplicate issues by (code, affected_columns)
        seen_keys = set()
        deduped_issues: list[IntelligenceIssue] = []
        for iss in issues:
            key = (iss.code, tuple(sorted(iss.affected_columns)))
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_issues.append(iss)

        # 10. Multi-analysis suitability evaluation
        mmm_suit = evaluate_mmm_suitability(
            temporal=structural.temporal,
            target=target_col,
            channels=channels,
            issues=deduped_issues,
            identifiability_risk=ident_risk,
        )

        panel_suit = evaluate_panel_mmm_suitability(
            temporal=structural.temporal,
            target=target_col,
            channels=channels,
            dimensions=dimensions,
            is_rectangular=True,
            market_count=market_report.market_count,
        )

        clv_suit = evaluate_clv_suitability(columns)

        suitability_map: dict[AnalysisType, SuitabilityAssessment] = {
            AnalysisType.MMM: mmm_suit,
            AnalysisType.PANEL_MMM: panel_suit,
            AnalysisType.CLV: clv_suit,
        }

        # 11. Transformation planning
        platform_col = next((col for col, inf in columns.items() if inf.semantic_type == "platform"), None)
        spend_col = next((col for col, inf in columns.items() if inf.semantic_type == "spend"), None)
        trans_plan = build_transformation_plan(
            df=df,
            date_column=structural.temporal.date_column,
            platform_col=platform_col,
            spend_col=spend_col,
            market_col=dimensions[0].column if dimensions else None,
            target_col=target_name,
        )

        # 12. Downstream Modeling Contract
        modeling_contract: ModelingContract | None = None
        if target_col and channels and structural.temporal.date_column:
            modeling_contract = ModelingContract(
                dataset_id=dataset_id,
                date_column=structural.temporal.date_column,
                target_column=target_col.column,
                channel_columns=[c.column for c in channels],
                control_columns=[c.column for c in controls],
                dims=dims,
                frequency=structural.temporal.frequency or "weekly",
                currency=target_col.currency or (currencies[0] if currencies else None),
                known_risks=ident_risk.factors,
                user_overrides_applied=user_overrides,
            )

        return SemanticDatasetContract(
            dataset_id=dataset_id,
            structural=structural,
            target=target_col,
            channels=channels,
            controls=controls,
            dimensions=dimensions,
            columns=columns,
            currencies=currencies,
            issues=deduped_issues,
            suitability=suitability_map,
            transformation_plan=trans_plan,
            clarification_requests=clarifications,
            modeling_contract=modeling_contract,
            user_overrides=user_overrides,
        )
