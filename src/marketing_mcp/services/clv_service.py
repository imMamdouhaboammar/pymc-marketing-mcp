"""
CLV Service — orchestrates CLV model lifecycle and predictions.

Mirrors ModelingService patterns: fit → persist → predict → churn.

Phase 3 — v0.5.0
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from marketing_mcp.adapters.clv_adapter import CLVAdapter
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import (
    CLVModelConfig,
    CLVModelRecord,
    FitCLVInput,
    PredictCLVInput,
)

if TYPE_CHECKING:
    from marketing_mcp.storage.metadata import SQLiteMetadataStore


class CLVService:
    """Orchestrates CLV model fitting, persistence, prediction, and churn analysis."""

    def __init__(
        self,
        metadata: SQLiteMetadataStore,
        artifact_dir: Path,
        adapter_cls: type[CLVAdapter] = CLVAdapter,
    ):
        self.metadata = metadata
        self.artifact_dir = Path(artifact_dir)
        self.adapter = adapter_cls()

    def _validate_rfm_data(self, df: pd.DataFrame, config: CLVModelConfig) -> None:
        """Validate RFM DataFrame against CLV model requirements."""
        required_cols = [
            config.customer_id_column,
            config.frequency_column,
            config.recency_column,
            config.T_column,
        ]
        if config.model_type == "gamma_gamma":
            if not config.monetary_value_column:
                raise DomainError(
                    "INVALID_CLV_CONFIG",
                    "gamma_gamma model requires monetary_value_column",
                    evidence={"model_type": config.model_type},
                    next_action="Set monetary_value_column in CLVModelConfig",
                )
            required_cols.append(config.monetary_value_column)

        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise DomainError(
                "MISSING_RFM_COLUMNS",
                f"Required RFM columns missing from dataset: {missing}",
                evidence={"missing": missing, "available": list(df.columns)},
                next_action="Ensure the dataset contains all required RFM columns",
            )

        # Validate non-negative numeric
        for col in [config.frequency_column, config.recency_column, config.T_column]:
            if (df[col] < 0).any():
                raise DomainError(
                    "INVALID_RFM_DATA",
                    f"Column '{col}' contains negative values — RFM values must be non-negative",
                    evidence={"column": col, "min_value": float(df[col].min())},
                    next_action="Fix negative values in the RFM dataset before fitting",
                )

        # Validate no duplicate customer IDs
        if df[config.customer_id_column].duplicated().any():
            n_dup = int(df[config.customer_id_column].duplicated().sum())
            raise DomainError(
                "DUPLICATE_CUSTOMER_IDS",
                f"customer_id_column '{config.customer_id_column}' has {n_dup} duplicate entries",
                evidence={"column": config.customer_id_column, "duplicate_count": n_dup},
                next_action="Aggregate to one row per customer before fitting CLV",
            )

        # Monetary non-negative
        if (
            config.monetary_value_column
            and config.monetary_value_column in df.columns
            and (df[config.monetary_value_column] < 0).any()
        ):
            raise DomainError(
                "INVALID_RFM_DATA",
                f"Column '{config.monetary_value_column}' contains negative values",
                evidence={"column": config.monetary_value_column},
                next_action="Fix negative monetary values in the RFM dataset",
            )

    def fit_clv(self, input: FitCLVInput) -> CLVModelRecord:
        """Fit a CLV model and persist metadata + artifact.

        Returns a CLVModelRecord with status 'completed'.
        """
        # Load and validate dataset
        try:
            ds_record = self.metadata.get_dataset(input.dataset_id)
        except DomainError:
            raise DomainError(
                "DATASET_NOT_FOUND",
                f"Dataset '{input.dataset_id}' not found",
                next_action="Register the dataset first with register_dataset",
            )

        df_path = Path(ds_record["path"])
        if not df_path.exists():
            raise DomainError("DATASET_FILE_MISSING", f"Dataset file not found: {df_path}")

        df = pd.read_parquet(df_path) if df_path.suffix == ".parquet" else pd.read_csv(df_path)
        self._validate_rfm_data(df, input.config)

        model_id = f"clv_{uuid.uuid4().hex[:12]}"
        artifact_path = self.artifact_dir / "clv" / f"{model_id}.nc"
        now = datetime.now(UTC).isoformat()

        # Build config dict for adapter
        config_dict = input.config.model_dump()

        self.adapter.fit(df, config_dict, artifact_path)

        # Build and persist record
        record = CLVModelRecord(
            model_id=model_id,
            model_type=input.config.model_type,
            dataset_id=input.dataset_id,
            status="completed",
            artifact_path=str(artifact_path),
            config=config_dict,
            package_provenance=self._get_provenance(),
            created_at=now,
            updated_at=now,
        )

        if self.metadata is not None:
            self.metadata.put_clv_model(record.model_dump())

        return record

    def predict_clv(self, input: PredictCLVInput) -> dict[str, Any]:
        """Load a fitted CLV model and return per-customer predictions."""
        from marketing_mcp.security import safe_identifier

        safe_identifier(input.model_id, "model")
        if self.metadata is None:
            raise DomainError("CLV_MODEL_NOT_FOUND", f"CLV model '{input.model_id}' not found")
        record = self.metadata.get_clv_model(input.model_id)

        artifact_path = Path(record["artifact_path"])
        model = self._load_clv_model(record["model_type"], artifact_path)
        return self.adapter.predict_clv(model, input.future_t, input.top_n_customers)

    def get_churn_risk_cohorts(self, model_id: str, threshold: float = 0.3) -> dict[str, Any]:
        """Return customers below P(alive) threshold for a fitted CLV model."""
        from marketing_mcp.security import safe_identifier

        safe_identifier(model_id, "model")
        if not (0.0 <= threshold <= 1.0):
            raise DomainError(
                "INVALID_THRESHOLD",
                f"threshold_p_alive must be between 0.0 and 1.0, got {threshold}",
                evidence={"threshold": threshold},
                next_action="Provide a probability threshold between 0.0 and 1.0",
            )
        if self.metadata is None:
            raise DomainError("CLV_MODEL_NOT_FOUND", f"CLV model '{model_id}' not found")
        record = self.metadata.get_clv_model(model_id)

        artifact_path = Path(record["artifact_path"])
        model = self._load_clv_model(record["model_type"], artifact_path)
        return self.adapter.churn_risk_cohorts(model, threshold_p_alive=threshold)

    def _load_clv_model(self, model_type: str, artifact_path: Path):
        """Load a CLV model artifact from disk."""
        model_cls = self.adapter._get_model_class(model_type)
        try:
            return model_cls.load(str(artifact_path))
        except Exception as e:
            raise DomainError(
                "CLV_ARTIFACT_LOAD_FAILED",
                f"Failed to load CLV artifact: {e}",
                evidence={"path": str(artifact_path)},
                next_action="Re-fit the CLV model",
            ) from e

    @staticmethod
    def _get_provenance() -> dict[str, str]:
        """Return package version provenance."""
        import importlib.metadata

        packages = ["pymc-marketing", "pymc", "arviz"]
        result = {}
        for pkg in packages:
            try:
                result[pkg] = importlib.metadata.version(pkg)
            except importlib.metadata.PackageNotFoundError:
                result[pkg] = "unknown"
        return result
