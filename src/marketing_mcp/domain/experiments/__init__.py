"""Experiment Evidence Registry package."""

from marketing_mcp.domain.experiments.models import (
    ExperimentMethodology,
    ExperimentRecord,
    RegisterExperimentInput,
)
from marketing_mcp.domain.experiments.registry import ExperimentRegistryService

__all__ = [
    "ExperimentMethodology",
    "ExperimentRecord",
    "RegisterExperimentInput",
    "ExperimentRegistryService",
]
