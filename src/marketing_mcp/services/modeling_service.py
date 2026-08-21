from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    CalibrateMMMInput,
    FitMMMInput,
    ModelRecord,
)


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _config_hash(config: dict[str, Any]) -> str:
    filtered = {k: v for k, v in config.items() if k not in {"sampler", "provenance"}}
    encoded = json.dumps(filtered, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


class ModelingService:
    def __init__(self, metadata, artifacts, datasets, adapter_factory):
        self.metadata = metadata
        self.artifacts = artifacts
        self.datasets = datasets
        self.adapter_factory = adapter_factory

    def fit(self, input: FitMMMInput) -> ModelRecord:
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

        rec = ModelRecord(
            model_id=model_id,
            parent_model_id=None,
            lineage_stage="initial_fit",
            dataset_id=input.dataset_id,
            dataset_fingerprint=fingerprint,
            semantic_config_hash=cfg_hash,
            status="running",
            config=config,
            package_provenance=versions,
            created_at=now,
            updated_at=now,
        )
        self.metadata.put_model(rec.model_dump())

        try:
            path = self.artifacts.model_path(model_id)
            adapter.fit(self.datasets.load(input.dataset_id), config, path)
            rec.status = "completed"
            rec.artifact_path = str(path)
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

    def calibrate(self, input: CalibrateMMMInput) -> ModelRecord:
        base_record = self.status(input.model_id)
        if base_record.status != "completed":
            raise DomainError(
                "MODEL_NOT_FITTED",
                "Base model has not completed fitting",
                evidence={"model_id": input.model_id, "status": base_record.status},
            )

        df_base = self.datasets.load(base_record.dataset_id)
        lift_records = []
        for test in input.lift_tests:
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
        cfg_hash = _config_hash(config)

        adapter = self.adapter_factory()
        versions = adapter.versions()

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
        )
        self.metadata.put_model(rec.model_dump())

        try:
            path = self.artifacts.model_path(calibrated_model_id)
            adapter.fit(df_base, config, path, lift_df=lift_df)
            rec.status = "completed"
            rec.artifact_path = str(path)
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

    def load_model(self, model_id: str):
        rec = self.status(model_id)
        if rec.status != "completed":
            raise DomainError(
                "MODEL_NOT_FITTED",
                "Model fitting has not completed",
                evidence={"status": rec.status},
            )
        return self.adapter_factory().load(self.artifacts.require(model_id)), rec
