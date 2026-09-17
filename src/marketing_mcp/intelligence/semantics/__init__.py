"""Semantic inference modules."""

from .channels import infer_channel_column
from .targets import infer_target_column
from .currencies import infer_currencies, verify_fx_consistency
from .objectives import analyze_campaign_objectives
from .roles import infer_all_column_roles

__all__ = [
    "infer_channel_column",
    "infer_target_column",
    "infer_currencies",
    "verify_fx_consistency",
    "analyze_campaign_objectives",
    "infer_all_column_roles",
]
