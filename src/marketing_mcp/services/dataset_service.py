from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset
from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.schemas.models import (
    DatasetInspection,
    DatasetRegistration,
    DatasetValidationResult,
    Finding,
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

    def list(self) -> list[dict[str, Any]]:
        return self.metadata.list_datasets()

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
            from marketing_mcp.accelerators import fast_sniff_and_validate_csv

            preflight = fast_sniff_and_validate_csv(raw)
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
        buffer = BytesIO(data)
        return pd.read_csv(buffer) if extension == ".csv" else pd.read_parquet(buffer)

    def load(self, dataset_id: str):
        record = self.metadata.get_dataset(dataset_id)
        blob = record.get("blob")
        if blob is None:
            path = Path(record["path"])
            return pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_parquet(path)
        ref = ArtifactRef(**blob)
        data = self.blobs.read_bytes(
            ref,
            owner=record.get("owner") or "local",
            tenant_id=record.get("tenant_id"),
        )
        return self._read_bytes(data, f".{record['format']}")

    def inspect(self, dataset_id: str) -> DatasetInspection:
        from marketing_mcp.scientific.datasets import inspect_dataset_frame

        df = self.load(dataset_id)
        return inspect_dataset_frame(df, dataset_id=dataset_id)

    def validate(
        self, dataset_id, date_column, target_column, channel_columns, control_columns, dims=None
    ) -> DatasetValidationResult:
        from marketing_mcp.scientific.datasets import validate_dataset_frame

        df = self.load(dataset_id)
        return validate_dataset_frame(
            df=df,
            date_column=date_column,
            target_column=target_column,
            channel_columns=channel_columns,
            control_columns=control_columns or [],
            dims=dims or [],
            dataset_id=dataset_id,
        )

    def summarize(
        self,
        dataset_id: str,
        date_column: str | None = None,
        channel_columns: list[str] | None = None,
        target_column: str | None = None,
    ):
        from marketing_mcp.scientific.datasets import summarize_dataset_frame

        df = self.load(dataset_id)
        return summarize_dataset_frame(
            df=df,
            date_column=date_column,
            channel_columns=channel_columns,
            target_column=target_column,
        )

