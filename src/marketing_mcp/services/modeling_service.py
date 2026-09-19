from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd

from marketing_mcp.domain.model_selection import compare_information_criteria
from marketing_mcp.errors import DomainError
from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.schemas.models import (
    CalibrateMMMInput,
    FitMMMInput,
    ModelComparisonInput,
    ModelRecord,
)


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _config_hash(config: dict[str, Any]) -> str:
    filtered = {k: v for k, v in config.items() if k not in {"sampler", "provenance"}}
    encoded = json.dumps(filtered, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


class ModelingService:
    def __init__(self, metadata, artifacts, datasets, adapter_factory: Any):
        self.metadata = metadata
        self.artifacts = artifacts
        self.datasets = datasets
        self.adapter_factory = adapter_factory

    def _fit_to_blob(
        self,
        adapter,
        dataframe,
        config: dict[str, Any],
        *,
        owner: str,
        tenant_id: str | None,
        lift_df=None,
    ) -> ArtifactRef:
        with TemporaryDirectory(prefix="marketing-mcp-fit-") as directory:
            path = Path(directory) / "model.nc"
            adapter.fit(dataframe, config, path, lift_df=lift_df)
            return self.artifacts.put_file(
                path,
                content_type="application/x-netcdf",
                owner=owner,
                tenant_id=tenant_id,
            )

    def fit(self, input: FitMMMInput, principal: Any = None, cancel_event: Any = None) -> ModelRecord:
        validation = self.datasets.validate(
            input.dataset_id,
            input.date_column,
            input.target_column,
            input.channel_columns,
            input.control_columns,
            input.dims,
        )
        if not validation.valid_for_modeling:
            raise DomainError(
                "INVALID_DATASET",
                "Dataset failed MMM validation",
                evidence={"findings": [f.model_dump() for f in validation.findings]},
                next_action="Fix dataset errors before fitting",
            )

        dataset_meta = self.metadata.get_dataset(input.dataset_id)
        fingerprint = dataset_meta.get("fingerprint", "") if dataset_meta else ""
        config = input.model_dump()
        cfg_hash = _config_hash(config)

        now = _utc()
        model_id = f"mmm_{uuid.uuid4().hex[:12]}"
        adapter = self.adapter_factory()
        versions = adapter.versions()

        owner = principal.subject if principal is not None else "local"
        tenant_id = principal.tenant_id if principal is not None else None

        requested_cfg = input.model_dump(exclude_unset=True)
        resolved_cfg = input.model_dump()
        from marketing_mcp.domain.configuration.transparency import build_config_audit
        audit = build_config_audit(requested_cfg, resolved_cfg, resolved_cfg)

        rec = ModelRecord(
            model_id=model_id,
            parent_model_id=None,
            lineage_stage="initial_fit",
            dataset_id=input.dataset_id,
            dataset_fingerprint=fingerprint,
            semantic_config_hash=cfg_hash,
            status="running",
            config=config,
            requested_config=requested_cfg,
            resolved_config=resolved_cfg,
            effective_config=resolved_cfg,
            config_diff=audit,
            package_provenance=versions,
            created_at=now,
            updated_at=now,
            owner=owner,
            tenant_id=tenant_id,
        )
        self.metadata.put_model(rec.model_dump())

        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            rec.status = "cancelled"
            rec.updated_at = _utc()
            self.metadata.put_model(rec.model_dump())
            raise DomainError("OPERATION_CANCELLED", "Model fitting was cancelled by client")

        try:
            artifact_ref = self._fit_to_blob(
                adapter,
                self.datasets.load(input.dataset_id),
                config,
                owner=owner,
                tenant_id=tenant_id,
            )
            if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
                rec.status = "cancelled"
                rec.updated_at = _utc()
                self.metadata.put_model(rec.model_dump())
                raise DomainError("OPERATION_CANCELLED", "Model fitting was cancelled by client")

            rec.status = "completed"
            rec.artifact_path = artifact_ref.uri
            rec.artifact_ref = asdict(artifact_ref)
            rec.updated_at = _utc()
            rec.config["provenance"] = versions
        except DomainError as e:
            rec.status = "failed"
            rec.failure = e.to_dict()["error"]
            rec.updated_at = _utc()
            self.metadata.put_model(rec.model_dump())
            raise
        except Exception as e:
            rec.status = "failed"
            rec.failure = {
                "code": "MODEL_FIT_FAILED",
                "message": str(e)[:1000],
                "type": type(e).__name__,
            }
            rec.updated_at = _utc()
            self.metadata.put_model(rec.model_dump())
            raise DomainError(
                "MODEL_FIT_FAILED",
                "PyMC-Marketing model fitting failed",
                evidence=rec.failure,
            ) from e

        self.metadata.put_model(rec.model_dump())
        return rec

    def calibrate(self, input: CalibrateMMMInput, principal: Any = None) -> ModelRecord:
        base_record = self.status(input.model_id)
        if base_record.status != "completed":
            raise DomainError(
                "MODEL_NOT_READY",
                f"Model {input.model_id} must be completed before calibration (current: {base_record.status})",
            )
        df_base = self.datasets.load(base_record.dataset_id)

        all_tests = list(input.lift_tests)
        if input.experiment_ids:
            from marketing_mcp.domain.experiments.registry import ExperimentRegistryService
            exp_service = ExperimentRegistryService(self.metadata)
            t_id = principal.tenant_id if principal is not None else getattr(base_record, "tenant_id", None)
            resolved_tests = exp_service.resolve_for_calibration(input.experiment_ids, tenant_id=t_id)
            all_tests.extend(resolved_tests)

        lift_records = []
        for test in all_tests:
            row: dict[str, Any] = {
                "channel": test.channel,
                "x": test.x,
                "delta_x": test.delta_x,
                "delta_y": test.delta_y,
                "sigma": test.sigma,
            }
            if test.geo:
                row["geo"] = test.geo
            lift_records.append(row)
        lift_df = pd.DataFrame(lift_records)

        now = _utc()
        calibrated_model_id = f"mmm_cal_{uuid.uuid4().hex[:10]}"
        config = dict(base_record.config)
        config["sampler"] = input.sampler.model_dump()
        if input.experiment_ids:
            config["calibration_experiment_ids"] = input.experiment_ids
        config["calibration_lift_tests_count"] = len(all_tests)
        cfg_hash = _config_hash(config)

        adapter = self.adapter_factory()
        versions = adapter.versions()

        owner = principal.subject if principal is not None else (getattr(base_record, "owner", None) or "local")
        tenant_id = principal.tenant_id if principal is not None else getattr(base_record, "tenant_id", None)

        rec = ModelRecord(
            model_id=calibrated_model_id,
            parent_model_id=input.model_id,
            lineage_stage="calibrated",
            dataset_id=base_record.dataset_id,
            dataset_fingerprint=base_record.dataset_fingerprint,
            semantic_config_hash=cfg_hash,
            status="running",
            config=config,
            package_provenance=versions,
            created_at=now,
            updated_at=now,
            owner=owner,
            tenant_id=tenant_id,
        )
        self.metadata.put_model(rec.model_dump())

        try:
            artifact_ref = self._fit_to_blob(
                adapter,
                df_base,
                config,
                owner=owner,
                tenant_id=tenant_id,
                lift_df=lift_df,
            )
            rec.status = "completed"
            rec.artifact_path = artifact_ref.uri
            rec.artifact_ref = asdict(artifact_ref)
            rec.updated_at = _utc()
            rec.config["provenance"] = versions
        except DomainError as e:
            rec.status = "failed"
            rec.failure = e.to_dict()["error"]
            rec.updated_at = _utc()
            self.metadata.put_model(rec.model_dump())
            raise
        except Exception as e:
            rec.status = "failed"
            rec.failure = {
                "code": "CALIBRATION_FAILED",
                "message": str(e)[:1000],
                "type": type(e).__name__,
            }
            rec.updated_at = _utc()
            self.metadata.put_model(rec.model_dump())
            raise DomainError(
                "CALIBRATION_FAILED",
                "PyMC-Marketing model calibration failed",
                evidence=rec.failure,
            ) from e

        self.metadata.put_model(rec.model_dump())
        return rec

    def compare_models(self, model_ids: list[str]) -> dict[str, Any]:
        records = [self.status(mid) for mid in model_ids]
        comparisons = []
        for rec in records:
            diag = rec.diagnostics or {}
            metrics = diag.get("diagnostics", {})
            comparisons.append(
                {
                    "model_id": rec.model_id,
                    "parent_model_id": rec.parent_model_id,
                    "lineage_stage": rec.lineage_stage,
                    "dataset_id": rec.dataset_id,
                    "status": rec.status,
                    "validation_state": rec.validation_state,
                    "divergences": metrics.get("divergences"),
                    "max_rhat": metrics.get("max_rhat"),
                    "min_ess_bulk": metrics.get("minimum_ess_bulk"),
                    "rmse": metrics.get("posterior_predictive_rmse"),
                    "nrmse": metrics.get("posterior_predictive_nrmse"),
                    "created_at": rec.created_at,
                }
            )
        return {
            "model_count": len(model_ids),
            "models": comparisons,
        }

    def archive_model(self, model_id: str) -> dict[str, Any]:
        rec = self.status(model_id)
        rec.status = "cancelled"
        rec.updated_at = _utc()
        self.metadata.put_model(rec.model_dump())
        return {
            "model_id": model_id,
            "status": "archived",
            "message": f"Model {model_id} has been archived",
        }

    def status(self, model_id: str) -> ModelRecord:
        data = self.metadata.get_model(model_id)
        if not data:
            raise DomainError("MODEL_NOT_FOUND", f"Model {model_id} was not found")
        return ModelRecord(**data)

    @contextmanager
    def materialized_model(self, model_id: str):
        rec = self.status(model_id)
        if rec.status != "completed":
            raise DomainError(
                "MODEL_NOT_FITTED",
                "Model fitting has not completed",
                evidence={"status": rec.status},
            )
        if rec.artifact_ref is None:
            yield self.adapter_factory().load(self.artifacts.require(model_id)), rec
            return
        ref = ArtifactRef(**rec.artifact_ref)
        with self.artifacts.materialize(
            ref,
            owner=rec.owner or "local",
            tenant_id=rec.tenant_id,
            suffix=".nc",
        ) as path:
            yield self.adapter_factory().load(path), rec

    def load_model(self, model_id: str):
        """Compatibility load; consumers with lazy models should use materialized_model."""
        with self.materialized_model(model_id) as loaded:
            return loaded

    def select_best_model(self, input: ModelComparisonInput) -> dict[str, Any]:
        records = [self.status(mid) for mid in input.model_ids]

        for rec in records:
            if rec.status != "completed":
                raise DomainError(
                    "MODEL_NOT_FITTED",
                    f"Model '{rec.model_id}' has not completed fitting (status: {rec.status})",
                    evidence={"model_id": rec.model_id, "status": rec.status},
                )

        dataset_ids = {rec.model_id: rec.dataset_id for rec in records}
        unique_datasets = set(dataset_ids.values())
        if len(unique_datasets) > 1:
            raise DomainError(
                "INCOMPATIBLE_MODELS",
                "All models must be fitted on the same dataset for comparative evaluation",
                evidence={"dataset_assignments": dataset_ids},
                next_action="Compare models fitted on the same dataset",
            )

        # Content identity wins over identifiers: forged-equal IDs must not
        # smuggle models fitted on different data into a comparison.
        dataset_fingerprints = {rec.model_id: rec.dataset_fingerprint for rec in records}
        unique_fingerprints = set(dataset_fingerprints.values())
        if len(unique_fingerprints) > 1:
            raise DomainError(
                "INCOMPATIBLE_MODELS",
                "Model comparison refused: dataset fingerprints differ even though "
                "dataset IDs match (dataset IDs may have been reassigned)",
                evidence={"dataset_fingerprints": dataset_fingerprints},
                next_action="Compare only models fitted on identical dataset contents",
            )

        loaded_models = {}
        for rec in records:
            model_obj, _ = self.load_model(rec.model_id)
            loaded_models[rec.model_id] = model_obj

        idatas = {mid: m.idata for mid, m in loaded_models.items()}
        result = compare_information_criteria(
            idatas=idatas,
            criterion=input.criterion,
            weighting=input.weighting,
        )
        return result.model_dump()
