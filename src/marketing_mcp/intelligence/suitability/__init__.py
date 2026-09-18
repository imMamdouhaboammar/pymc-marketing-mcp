"""Analysis suitability evaluators."""

from .clv import evaluate_clv_suitability
from .evaluator import assess_suitability
from .mmm import evaluate_mmm_suitability
from .panel_mmm import evaluate_panel_mmm_suitability

__all__ = [
    "evaluate_mmm_suitability",
    "evaluate_panel_mmm_suitability",
    "evaluate_clv_suitability",
    "assess_suitability",
]
