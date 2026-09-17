"""CLV Service — orchestrates CLV model lifecycle and predictions.

Provides model-specific endpoints for purchase models (BG/NBD, sBG),
value models (Gamma-Gamma), combined CLV estimation, and churn analysis.
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack, contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any

import pandas as pd

from marketing_mcp.adapters.clv_adapter import CLVAdapter
from marketing_mcp.errors import DomainError
from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.schemas.models import (
    CLVModelConfig,
    CLVModelRecord,
    EstimateCLVInput,
    FitCLVInput,
    FitPurchaseModelInput,
    FitValueModelInput,
    ModelLineage,
    PredictCLVInput,
    PredictExpectedPurchasesInput,
    PredictExpectedSpendInput,
    PredictProbabilityAliveInput,
)
from marketing_mcp.security import safe_identifier
from marketing_mcp.storage.artifacts import LocalArtifactStore

if TYPE_CHECKING:
    from marketing_mcp.repositories.base import MetadataRepository


class CLVService:
    """Orchestrates CLV model fitting, persistence, prediction, and lifetime value estimation."""

    def __init__(
        self,
        metadata: MetadataRepository,
        artifact_dir: LocalArtifactStore | Path,
        adapter_cls: type[CLVAdapter] = CLVAdapter,
        datasets=None,
    ):
        self.metadata = metadata
        self.artifacts = (
            artifact_dir
            if isinstance(artifact_dir, LocalArtifactStore)
            else LocalArtifactStore(artifact_dir)
        )
        self.datasets = datasets
        self.adapter = adapter_cls()

    def _load_dataset(self, dataset_id: str) -> pd.DataFrame:
        """Load dataset through shared verified storage when configured."""
        if self.datasets is not None:
            return self.datasets.load(dataset_id)
        try:
            dataset = self.metadata.get_dataset(dataset_id)
        except DomainError:
            raise DomainError(
                "DATASET_NOT_FOUND",
                f"Dataset '{dataset_id}' not found",
                next_action="Register the dataset first with register_dataset",
            )
        path = Path(dataset["path"])
        if not path.exists():
            raise DomainError("DATASET_FILE_MISSING", f"Dataset file not found: {path}")
        return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)

    def _fit_to_blob(
        self, dataframe: pd.DataFrame, config: dict[str, Any], model_id: str, dataset_id: str
    ):
        dataset = self.metadata.get_dataset(dataset_id)
        owner = dataset.get("owner") or "local"
        tenant_id = dataset.get("tenant_id")
        with TemporaryDirectory(prefix="marketing-mcp-clv-") as directory:
            path = Path(directory) / f"{model_id}.nc"
            self.adapter.fit(dataframe, config, path)
            ref = self.artifacts.put_file(
                path,
                content_type="application/x-netcdf",
                owner=owner,
                tenant_id=tenant_id,
            )
        return ref, owner, tenant_id

    def _validate_rfm_data(self, df: pd.DataFrame, config: CLVModelConfig) -> None:
        """Validate RFM DataFrame against CLV model requirements."""
        self.adapter.normalize_data(df, config.model_type, config.model_dump())

    def _build_lineage(
        self,
        dataset_id: str,
        df: pd.DataFrame,
        model_family: str,
        cust_col: str | None = None,
        now: str | None = None,
        currency: str | None = None,
        value_unit: str | None = None,
    ) -> ModelLineage:
        import hashlib

        dataset_meta = self.metadata.get_dataset(dataset_id) if self.metadata else {}
        fingerprint = (
            dataset_meta.get("fingerprint")
            or dataset_meta.get("sha256")
            or f"rows_{len(df)}_cols_{len(df.columns)}"
        )
        cust_pop_fp = ""
        if cust_col and cust_col in df.columns:
            cust_ids = sorted(str(x) for x in df[cust_col].dropna().unique())
            cust_pop_fp = hashlib.sha256("||".join(cust_ids).encode("utf-8")).hexdigest()

        return ModelLineage(
            dataset_id=dataset_id,
            dataset_fingerprint=fingerprint,
            customer_id_column=cust_col or "",
            customer_population_fingerprint=cust_pop_fp,
            currency=currency or dataset_meta.get("currency"),
            value_unit=value_unit or dataset_meta.get("value_unit"),
            model_family=model_family,
            training_timestamp=now or datetime.now(UTC).isoformat(),
        )

    def fit_purchase_model(self, input: FitPurchaseModelInput) -> CLVModelRecord:
        """Fit a repeat purchase model (BG/NBD or ShiftedBetaGeo) and persist artifact."""
        df = self._load_dataset(input.dataset_id)
        model_id = f"clv_p_{uuid.uuid4().hex[:10]}"
        now = datetime.now(UTC).isoformat()

        config_dict = input.model_dump()
        artifact_ref, owner, tenant_id = self._fit_to_blob(
            df, config_dict, model_id, input.dataset_id
        )

        lineage = self._build_lineage(
            dataset_id=input.dataset_id,
            df=df,
            model_family=input.model_type,
            cust_col=input.customer_id_col,
            now=now,
        )

        record = CLVModelRecord(
            model_id=model_id,
            model_type=input.model_type,
            dataset_id=input.dataset_id,
            dataset_fingerprint=lineage.dataset_fingerprint,
            lineage=lineage,
            status="completed",
            artifact_path=artifact_ref.uri,
            artifact_ref=asdict(artifact_ref),
            config=config_dict,
            package_provenance=self._get_provenance(),
            created_at=now,
            updated_at=now,
            owner=owner,
            tenant_id=tenant_id,
        )

        if self.metadata is not None:
            self.metadata.put_clv_model(record.model_dump())

        return record

    def fit_value_model(self, input: FitValueModelInput) -> CLVModelRecord:
        """Fit a monetary value transaction model (Gamma-Gamma) and persist artifact."""
        df = self._load_dataset(input.dataset_id)
        model_id = f"clv_v_{uuid.uuid4().hex[:10]}"
        now = datetime.now(UTC).isoformat()

        config_dict = input.model_dump()
        artifact_ref, owner, tenant_id = self._fit_to_blob(
            df, config_dict, model_id, input.dataset_id
        )

        lineage = self._build_lineage(
            dataset_id=input.dataset_id,
            df=df,
            model_family=input.model_type,
            cust_col=input.customer_id_col,
            now=now,
        )

        record = CLVModelRecord(
            model_id=model_id,
            model_type=input.model_type,
            dataset_id=input.dataset_id,
            dataset_fingerprint=lineage.dataset_fingerprint,
            lineage=lineage,
            status="completed",
            artifact_path=artifact_ref.uri,
            artifact_ref=asdict(artifact_ref),
            config=config_dict,
            package_provenance=self._get_provenance(),
            created_at=now,
            updated_at=now,
            owner=owner,
            tenant_id=tenant_id,
        )

        if self.metadata is not None:
            self.metadata.put_clv_model(record.model_dump())

        return record

    def fit_clv(self, input: FitCLVInput) -> CLVModelRecord:
        """Legacy compatibility method to fit any CLV model."""
        df = self._load_dataset(input.dataset_id)
        model_id = f"clv_{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC).isoformat()

        config_dict = input.config.model_dump()
        artifact_ref, owner, tenant_id = self._fit_to_blob(
            df, config_dict, model_id, input.dataset_id
        )

        lineage = self._build_lineage(
            dataset_id=input.dataset_id,
            df=df,
            model_family=input.config.model_type,
            cust_col=input.config.customer_id_column,
            now=now,
        )

        record = CLVModelRecord(
            model_id=model_id,
            model_type=input.config.model_type,
            dataset_id=input.dataset_id,
            dataset_fingerprint=lineage.dataset_fingerprint,
            lineage=lineage,
            status="completed",
            artifact_path=artifact_ref.uri,
            artifact_ref=asdict(artifact_ref),
            config=config_dict,
            package_provenance=self._get_provenance(),
            created_at=now,
            updated_at=now,
            owner=owner,
            tenant_id=tenant_id,
        )

        if self.metadata is not None:
            self.metadata.put_clv_model(record.model_dump())

        return record

    @contextmanager
    def _materialized_model(self, record: dict[str, Any]):
        blob = record.get("artifact_ref")
        if blob is None:
            yield self._load_clv_model(record["model_type"], Path(record["artifact_path"]))
            return
        ref = ArtifactRef(**blob)
        with self.artifacts.materialize(
            ref,
            owner=record.get("owner") or "local",
            tenant_id=record.get("tenant_id"),
            suffix=".nc",
        ) as path:
            yield self._load_clv_model(record["model_type"], path)

    def predict_expected_purchases(self, input: PredictExpectedPurchasesInput) -> dict[str, Any]:
        """Predict expected future purchases for customers using a purchase model."""
        safe_identifier(input.model_id, "model")
        record = self._require_clv_model_record(input.model_id)
        if record["model_type"] not in ("bg_nbd", "shifted_beta_geo"):
            raise DomainError(
                "INVALID_MODEL_TYPE",
                f"Model '{input.model_id}' is of type '{record['model_type']}', expected purchase model ('bg_nbd')",
                evidence={"model_id": input.model_id, "model_type": record["model_type"]},
            )
        with self._materialized_model(record) as model:
            return self.adapter.predict_expected_purchases(
                model, future_t=input.future_t, top_n=input.top_n
            )

    def predict_probability_alive(self, input: PredictProbabilityAliveInput) -> dict[str, Any]:
        """Predict probability of customer alive using a purchase or churn model."""
        safe_identifier(input.model_id, "model")
        record = self._require_clv_model_record(input.model_id)
        with self._materialized_model(record) as model:
            return self.adapter.predict_probability_alive(model, top_n=input.top_n)

    def predict_expected_spend(self, input: PredictExpectedSpendInput) -> dict[str, Any]:
        """Predict expected transaction spend for customers using a Gamma-Gamma value model."""
        safe_identifier(input.model_id, "model")
        record = self._require_clv_model_record(input.model_id)
        if record["model_type"] != "gamma_gamma":
            raise DomainError(
                "INVALID_MODEL_TYPE",
                f"Model '{input.model_id}' is of type '{record['model_type']}', expected value model ('gamma_gamma')",
                evidence={"model_id": input.model_id, "model_type": record["model_type"]},
            )
        with self._materialized_model(record) as model:
            return self.adapter.predict_expected_spend(model, top_n=input.top_n)

    def estimate_customer_lifetime_value(self, input: EstimateCLVInput) -> dict[str, Any]:
        """Estimate combined discounted CLV using a purchase model and a value model."""
        safe_identifier(input.purchase_model_id, "model")
        safe_identifier(input.value_model_id, "model")

        p_rec = self._require_clv_model_record(input.purchase_model_id)
        v_rec = self._require_clv_model_record(input.value_model_id)

        if p_rec["model_type"] not in ("bg_nbd", "shifted_beta_geo"):
            raise DomainError(
                "INCOMPATIBLE_MODELS",
                f"purchase_model_id '{input.purchase_model_id}' must be a purchase model (got '{p_rec['model_type']}')",
            )
        if v_rec["model_type"] != "gamma_gamma":
            raise DomainError(
                "INCOMPATIBLE_MODELS",
                f"value_model_id '{input.value_model_id}' must be a Gamma-Gamma value model (got '{v_rec['model_type']}')",
            )

        # Validate lineage, currency, and cohort consistency (CLV-001)
        p_lineage = p_rec.get("lineage") or {}
        v_lineage = v_rec.get("lineage") or {}

        def _get_field(rec_dict: dict, lin: Any, key: str):
            val = rec_dict.get(key)
            if val:
                return val
            if isinstance(lin, dict):
                return lin.get(key)
            return getattr(lin, key, None)

        p_fp = _get_field(p_rec, p_lineage, "dataset_fingerprint")
        v_fp = _get_field(v_rec, v_lineage, "dataset_fingerprint")
        p_ds = _get_field(p_rec, p_lineage, "dataset_id") or _get_field(p_rec, p_lineage, "source_dataset_id")
        v_ds = _get_field(v_rec, v_lineage, "dataset_id") or _get_field(v_rec, v_lineage, "source_dataset_id")
        p_pop = _get_field(p_rec, p_lineage, "customer_population_fingerprint")
        v_pop = _get_field(v_rec, v_lineage, "customer_population_fingerprint")
        p_curr = _get_field(p_rec, p_lineage, "currency")
        v_curr = _get_field(v_rec, v_lineage, "currency")

        # Fail-closed validation on dataset lineage: missing or mismatched dataset metadata triggers rejection
        if not p_ds or not v_ds or p_ds != v_ds or not p_fp or not v_fp or p_fp != v_fp:
            raise DomainError(
                "CLV_LINEAGE_MISMATCH",
                f"Purchase model '{input.purchase_model_id}' and value model '{input.value_model_id}' were trained on different or unverified datasets/cohorts ({p_ds} vs {v_ds})",
                evidence={
                    "purchase_model_id": input.purchase_model_id,
                    "value_model_id": input.value_model_id,
                    "purchase_dataset_id": p_ds,
                    "value_dataset_id": v_ds,
                    "purchase_fingerprint": p_fp,
                    "value_fingerprint": v_fp,
                },
                next_action="Ensure both models are trained on the same customer transaction dataset",
            )

        # Monetary currency unit validation
        if p_curr and v_curr and str(p_curr).strip().upper() != str(v_curr).strip().upper():
            raise DomainError(
                "CLV_CURRENCY_MISMATCH",
                f"Purchase model currency '{p_curr}' does not match value model currency '{v_curr}'",
                evidence={"purchase_currency": p_curr, "value_currency": v_curr},
                next_action="Ensure both models use the same currency units",
            )

        # Customer cohort population validation
        if p_pop and v_pop and p_pop != v_pop:
            raise DomainError(
                "CLV_COHORT_MISMATCH",
                "Purchase model customer cohort does not match value model customer cohort",
                evidence={"purchase_cohort_fingerprint": p_pop, "value_cohort_fingerprint": v_pop},
                next_action="Ensure both models are trained on the exact same customer cohort",
            )

        with ExitStack() as stack:
            purchase_model = stack.enter_context(self._materialized_model(p_rec))
            value_model = stack.enter_context(self._materialized_model(v_rec))
            return self.adapter.estimate_customer_lifetime_value(
                purchase_model=purchase_model,
                value_model=value_model,
                future_t=input.future_t,
                discount_rate=input.discount_rate,
                top_n=input.top_n,
            )

    def predict_clv(self, input: PredictCLVInput) -> dict[str, Any]:
        """Legacy prediction method."""
        safe_identifier(input.model_id, "model")
        record = self._require_clv_model_record(input.model_id)
        with self._materialized_model(record) as model:
            return self.adapter.predict_clv(model, input.future_t, input.top_n_customers)

    def get_churn_risk_cohorts(self, model_id: str, threshold: float = 0.3) -> dict[str, Any]:
        """Return customers below P(alive) threshold for a fitted CLV model."""
        safe_identifier(model_id, "model")
        if not (0.0 <= threshold <= 1.0):
            raise DomainError(
                "INVALID_THRESHOLD",
                f"threshold_p_alive must be between 0.0 and 1.0, got {threshold}",
                evidence={"threshold": threshold},
                next_action="Provide a probability threshold between 0.0 and 1.0",
            )
        record = self._require_clv_model_record(model_id)
        with self._materialized_model(record) as model:
            return self.adapter.churn_risk_cohorts(model, threshold_p_alive=threshold)

    def _require_clv_model_record(self, model_id: str) -> dict[str, Any]:
        if self.metadata is None:
            raise DomainError("CLV_MODEL_NOT_FOUND", f"CLV model '{model_id}' not found")
        try:
            return self.metadata.get_clv_model(model_id)
        except DomainError:
            try:
                rec = self.metadata.get_model(model_id)
                if rec.get("model_family") == "clv" or rec.get("model_type") in ("bg_nbd", "gamma_gamma", "shifted_beta_geo"):
                    return rec
            except DomainError:
                pass
            raise DomainError("CLV_MODEL_NOT_FOUND", f"CLV model '{model_id}' not found")

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
