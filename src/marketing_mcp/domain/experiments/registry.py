"""Experiment Evidence Registry domain service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from marketing_mcp.domain.experiments.models import (
    ExperimentRecord,
    RegisterExperimentInput,
)
from marketing_mcp.errors import DomainError
from marketing_mcp.repositories.base import MetadataRepository
from marketing_mcp.schemas.models import LiftTestMeasurement


class ExperimentRegistryService:
    """Service managing persistent, tenant-isolated experiment evidence."""

    def __init__(self, metadata: MetadataRepository):
        self.metadata = metadata

    def register(
        self,
        input_data: RegisterExperimentInput,
        tenant_id: str | None = None,
    ) -> ExperimentRecord:
        """Register an experiment in the evidence registry.

        Enforces non-negative spend and uncertainty, generates immutable provenance,
        and ensures tenant isolation.
        """
        now = datetime.now(UTC).isoformat()
        t_id = tenant_id or input_data.tenant_id or "default"

        payload: dict[str, Any] = {
            "experiment_id": input_data.experiment_id,
            "channel": input_data.channel,
            "geo": input_data.geo,
            "methodology": input_data.methodology,
            "start_date": input_data.start_date,
            "end_date": input_data.end_date,
            "treatment_description": input_data.treatment_description,
            "baseline_spend": float(input_data.baseline_spend),
            "spend_delta": float(input_data.spend_delta),
            "measured_incremental_response": float(input_data.measured_incremental_response),
            "standard_error": float(input_data.standard_error),
            "evidence_quality_score": float(input_data.evidence_quality_score),
            "source": input_data.source,
            "tenant_id": t_id,
            "project_id": input_data.project_id,
            "archived": False,
            "created_at": now,
            "provenance": {
                "registered_at": now,
                "tenant_id": t_id,
                "generator": "ExperimentRegistryService",
            },
        }

        self.metadata.put_experiment(payload, tenant_id=t_id)
        return ExperimentRecord(**payload)

    def get(self, experiment_id: str, tenant_id: str | None = None) -> ExperimentRecord:
        payload = self.metadata.get_experiment(experiment_id, tenant_id=tenant_id)
        return ExperimentRecord(**payload)

    def list_all(
        self,
        tenant_id: str | None = None,
        channel: str | None = None,
        include_archived: bool = False,
    ) -> list[ExperimentRecord]:
        items = self.metadata.list_experiments(
            tenant_id=tenant_id,
            channel=channel,
            include_archived=include_archived,
        )
        return [ExperimentRecord(**item) for item in items]

    def archive(self, experiment_id: str, tenant_id: str | None = None) -> None:
        self.metadata.archive_experiment(experiment_id, tenant_id=tenant_id)

    def resolve_for_calibration(
        self,
        experiment_ids: list[str],
        tenant_id: str | None = None,
    ) -> list[LiftTestMeasurement]:
        """Convert a list of registered experiment IDs into LiftTestMeasurement objects.

        Raises DomainError if any experiment is archived or missing.
        """
        measurements: list[LiftTestMeasurement] = []
        for exp_id in experiment_ids:
            rec = self.get(exp_id, tenant_id=tenant_id)
            if rec.archived:
                raise DomainError(
                    "EXPERIMENT_ARCHIVED",
                    f"Experiment '{exp_id}' has been archived and cannot be used for active calibration",
                    evidence={"experiment_id": exp_id},
                    next_action="Use an active experiment ID or unarchive this record",
                )
            measurements.append(
                LiftTestMeasurement(
                    channel=rec.channel,
                    geo=rec.geo,
                    x=rec.baseline_spend,
                    delta_x=rec.spend_delta,
                    delta_y=rec.measured_incremental_response,
                    sigma=rec.standard_error,
                    description=f"ExperimentRegistry:{rec.experiment_id}",
                )
            )
        return measurements
