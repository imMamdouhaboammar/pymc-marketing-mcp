from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from marketing_mcp.errors import DomainError
from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.schemas.models import (
    DatasetInspection,
    DatasetRegistration,
    DatasetValidationResult,
)
from marketing_mcp.security import safe_source_path
from marketing_mcp.storage.artifacts import LocalArtifactStore


def _utc():
    return datetime.now(UTC).isoformat()


class DatasetService:
    def __init__(
        self, metadata, storage: LocalArtifactStore | Path, max_dataset_mb: int = 100
    ):
        self.metadata = metadata
        self.blobs = storage if isinstance(storage, LocalArtifactStore) else LocalArtifactStore(storage)
        self.max_bytes = max_dataset_mb * 1024 * 1024

    def list(self, principal: Any = None) -> list[dict[str, Any]]:
        tenant_id = principal.tenant_id if principal and principal.auth_type != "stdio" else None
        return self.metadata.list_datasets(tenant_id=tenant_id)

    def register_bytes(
        self,
        raw: bytes,
        format: str = "csv",
        filename: str | None = None,
        principal: Any = None,
    ) -> DatasetRegistration:
        from marketing_mcp.errors import DomainError

        if len(raw) > self.max_bytes:
            raise DomainError(
                "DATASET_TOO_LARGE",
                f"Dataset exceeds maximum allowed size of {self.max_bytes} bytes",
                evidence={"size_bytes": len(raw), "max_bytes": self.max_bytes},
                next_action="Pre-aggregate or filter dataset to reduce size before registering",
            )
        fmt = format.lower().lstrip(".")
        if fmt not in {"csv", "parquet"}:
            raise DomainError(
                "UNSUPPORTED_DATASET_FORMAT",
                f"Unsupported format '{format}'. Only CSV and Parquet are supported",
                evidence={"provided_format": format},
                next_action="Provide dataset in CSV or Parquet format",
            )
        extension = f".{fmt}"
        if fmt == "csv":
            stripped = raw.lstrip()
            if stripped.startswith((b"<!doctype", b"<!DOCTYPE", b"<html", b"<HTML", b"<head", b"<body", b"<?xml")):
                raise DomainError(
                    "INVALID_DATASET_CONTENT",
                    "Provided file content appears to be an HTML or XML document, not a tabular CSV",
                    evidence={"prefix": raw[:100].decode("utf-8", errors="replace")},
                    next_action="Provide tabular CSV or Parquet data",
                )
            if stripped.startswith(b"{") and stripped.rstrip().endswith(b"}"):
                raise DomainError(
                    "INVALID_DATASET_CONTENT",
                    "Provided file content appears to be JSON markup, not a tabular CSV",
                    evidence={"prefix": raw[:100].decode("utf-8", errors="replace")},
                    next_action="Provide tabular CSV or Parquet data",
                )
            from marketing_mcp.accelerators import fast_sniff_and_validate_csv

            try:
                preflight = fast_sniff_and_validate_csv(raw)
            except Exception as e:
                raise DomainError(
                    "INVALID_DATASET_CONTENT",
                    f"Failed to parse CSV dataset: {e}",
                    evidence={"error": str(e)},
                    next_action="Ensure CSV data is properly formatted",
                ) from e
            if len(preflight.get("column_names", [])) < 2:
                raise DomainError(
                    "INVALID_DATASET_CONTENT",
                    "Dataset must contain at least two columns (e.g. date and target/channel)",
                    evidence={"columns": preflight.get("column_names", [])},
                    next_action="Provide tabular CSV data with headers and multiple columns",
                )
            row_count = preflight["row_count"]
        else:
            frame = self._read_bytes(raw, extension)
            row_count = len(frame)

        fingerprint = hashlib.sha256(raw).hexdigest()
        owner = principal.subject if principal is not None else "local"
        tenant_id = principal.tenant_id if principal is not None else None
        identity = f"{tenant_id or 'local'}\0{owner}\0{fingerprint}".encode()
        dataset_id = f"dataset_{hashlib.sha256(identity).hexdigest()[:12]}"
        ref = self.blobs.put_bytes(
            raw,
            content_type="text/csv" if fmt == "csv" else "application/x-parquet",
            owner=owner,
            tenant_id=tenant_id,
        )
        record = DatasetRegistration(
            dataset_id=dataset_id,
            path=ref.uri,
            fingerprint=fingerprint,
            format=fmt,
            rows=row_count,
            created_at=_utc(),
            owner=owner,
            tenant_id=tenant_id,
            blob=asdict(ref),
        )
        self.metadata.put_dataset(record.model_dump())
        return record

    def register_file(self, source: Path, principal: Any = None) -> DatasetRegistration:
        source = safe_source_path(Path(source), self.max_bytes)
        raw = source.read_bytes()
        extension = source.suffix.lower()
        return self.register_bytes(
            raw,
            format=extension.lstrip("."),
            filename=source.name,
            principal=principal,
        )

    @staticmethod
    def _read_bytes(data: bytes, extension: str):
        if not data or len(data.strip()) == 0:
            raise DomainError(
                "DATASET_EMPTY",
                "Dataset contains no data",
                next_action="Provide a non-empty CSV or Parquet file",
            )
        buffer = BytesIO(data)
        try:
            df = pd.read_csv(buffer) if extension == ".csv" else pd.read_parquet(buffer)
        except Exception as exc:
            raise DomainError(
                "DATASET_PARSE_FAILED",
                f"Failed to parse {extension} dataset: {exc}",
                evidence={"extension": extension, "error": str(exc)},
                next_action="Ensure the dataset is a valid, well-formed CSV or Parquet file",
            ) from exc
        return df

    def load(self, dataset_id: str, principal: Any = None):
        tenant_id = principal.tenant_id if principal and principal.auth_type != "stdio" else None
        record = self.metadata.get_dataset(dataset_id, tenant_id=tenant_id)
        blob = record.get("blob")
        if blob is None:
            path = Path(record["path"])
            try:
                df = pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_parquet(path)
            except Exception as exc:
                raise DomainError(
                    "DATASET_PARSE_FAILED",
                    f"Failed to parse dataset file: {exc}",
                    evidence={"path": str(path), "error": str(exc)},
                    next_action="Ensure the file is a valid CSV or Parquet file",
                ) from exc
            return df
        ref = ArtifactRef(**blob)
        data = self.blobs.read_bytes(
            ref,
            owner=record.get("owner") or "local",
            tenant_id=record.get("tenant_id"),
        )
        return self._read_bytes(data, f".{record['format']}")

    def inspect(
        self,
        dataset_id: str,
        principal: Any = None,
        user_overrides: dict[str, Any] | None = None,
        analysis_type: str = "mmm",
    ) -> DatasetInspection:
        df = self.load(dataset_id, principal=principal)
        from marketing_mcp.scientific.datasets import inspect_dataset_frame
        return inspect_dataset_frame(
            df,
            dataset_id=dataset_id,
            user_overrides=user_overrides,
            analysis_type=analysis_type,
        )

    def validate(
        self,
        dataset_id: str,
        date_column: str,
        target_column: str,
        channel_columns: list[str],
        control_columns: list[str] | None = None,
        dims: list[str] | None = None,
        principal: Any = None,
        user_overrides: dict[str, Any] | None = None,
    ) -> DatasetValidationResult:
        df = self.load(dataset_id, principal=principal)
        from marketing_mcp.scientific.datasets import validate_dataset_frame
        return validate_dataset_frame(
            df=df,
            date_column=date_column,
            target_column=target_column,
            channel_columns=channel_columns,
            control_columns=control_columns or [],
            dims=dims or [],
            dataset_id=dataset_id,
            user_overrides=user_overrides,
        )

    def transform_long_form(
        self,
        dataset_id: str,
        date_column: str,
        channel_column: str,
        spend_column: str,
        target_columns: list[str],
        dimension_columns: list[str] | None = None,
        frequency: str = "D",
        principal: Any = None,
        cancel_event: Any = None,
    ):
        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            raise DomainError("OPERATION_CANCELLED", "Transformation was cancelled by client")
        from marketing_mcp.scientific.transformations import (
            generate_transformation_plan,
            transform_long_form_export,
        )

        raw_df = self.load(dataset_id, principal=principal)
        plan = generate_transformation_plan(
            raw_df,
            date_column=date_column,
            channel_column=channel_column,
            spend_column=spend_column,
            target_columns=target_columns,
            dimension_columns=dimension_columns,
            frequency=frequency,
        )
        transformed_df, provenance = transform_long_form_export(raw_df, plan)
        if cancel_event and getattr(cancel_event, "is_set", lambda: False)():
            raise DomainError("OPERATION_CANCELLED", "Transformation was cancelled by client")
        transformed_bytes = transformed_df.to_csv(index=False).encode("utf-8")
        registered = self.register_bytes(
            transformed_bytes,
            format="csv",
            filename=f"transformed_{dataset_id}.csv",
            principal=principal,
        )
        return registered, provenance, plan


