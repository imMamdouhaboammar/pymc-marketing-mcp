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

        loaded_models = {}
        for rec in records:
            model_obj, _ = self.load_model(rec.model_id)
            loaded_models[rec.model_id] = model_obj

        import arviz as az

        compare_dict = {mid: m.idata for mid, m in loaded_models.items()}
        method = input.method
        stacking_method = "BB-pseudo-BMA" if method == "waic" else "stacking"

        try:
            comp_df = az.compare(compare_dict, method=stacking_method)
        except Exception as e:
            raise DomainError(
                "MODEL_COMPARISON_FAILED",
                f"Information-theoretic model comparison failed: {e}",
                evidence={"error": str(e)[:500], "method": method},
            ) from e

        ranked_models = []
        best_model_id = str(comp_df.index[0])
        stacking_weights = {}

        for mid in comp_df.index:
            row = comp_df.loc[mid]
            w = float(row.get("weight", 0.0))
            stacking_weights[str(mid)] = round(w, 4)
            ranked_models.append(
                {
                    "model_id": str(mid),
                    "rank": int(row.get("rank", 0)),
                    "elpd_diff": float(round(float(row.get("elpd_diff", 0.0)), 4)),
                    "dse": float(round(float(row.get("dse", 0.0)), 4)),
                    "elpd": float(round(float(row.get("elpd", 0.0)), 4)),
                    "se": float(round(float(row.get("se", 0.0)), 4)),
                    "weight": round(w, 4),
                }
            )

        pareto_k_warnings = []
        for mid, m in loaded_models.items():
            try:
                loo_res = az.loo(m.idata)
                if hasattr(loo_res, "pareto_k"):
                    import numpy as np

                    pk_vals = np.asarray(loo_res.pareto_k).flatten()
                    high_k = pk_vals[pk_vals > 0.7]
                    if len(high_k) > 0:
                        pareto_k_warnings.append(
                            {
                                "code": "HIGH_PARETO_K",
                                "model_id": mid,
                                "severity": "warning",
                                "high_k_count": len(high_k),
                                "max_k": float(round(float(np.max(pk_vals)), 4)),
                                "message": f"Model {mid} has {len(high_k)} observations with Pareto-k > 0.7.",
                            }
                        )
            except (KeyError, ValueError, AttributeError, TypeError):
                pass

        interpretation = (
            f"Best model based on expected log pointwise predictive density (ELPD) is '{best_model_id}'. "
            "Bayesian stacking distributes predictive weight across specifications according to out-of-sample capability."
        )

        return {
            "method": method,
            "best_model_id": best_model_id,
            "ranked_models": ranked_models,
            "stacking_weights": stacking_weights,
            "pareto_k_warnings": pareto_k_warnings,
            "interpretation": interpretation,
        }
