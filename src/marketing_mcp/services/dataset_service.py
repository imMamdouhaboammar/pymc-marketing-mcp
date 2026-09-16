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

    def load(self, dataset_id: str):
        record = self.metadata.get_dataset(dataset_id)
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

    def inspect(self, dataset_id: str) -> DatasetInspection:
        df = self.load(dataset_id)
        possible_dates = []
        for c in df.columns:
            if "date" in c.lower() or "week" in c.lower():
                possible_dates.append(c)
        date_col = possible_dates[0] if possible_dates else None
        freq = None
        start = end = None
        missing = []
        issues = []
        if date_col:
            dates = (
                pd.to_datetime(df[date_col], errors="coerce")
                .dropna()
                .sort_values()
                .drop_duplicates()
            )
            start = dates.min().date().isoformat() if len(dates) else None
            end = dates.max().date().isoformat() if len(dates) else None
            if len(dates) >= 3:
                deltas = dates.diff().dropna().dt.days
                med = float(deltas.median())
                freq = (
                    "daily"
                    if med <= 1.5
                    else "weekly"
                    if med <= 8
                    else "monthly"
                    if med <= 35
                    else "irregular"
                )
                if freq == "weekly":
                    expected = pd.date_range(
                        dates.min(), dates.max(), freq=pd.Timedelta(days=round(med))
                    )
                    missing = [d.date().isoformat() for d in expected.difference(dates)[:100]]
        numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        targets = [
            c
            for c in numeric
            if any(k in c.lower() for k in ["revenue", "sales", "orders", "target", "conversion"])
        ]
        channels = [
            c
            for c in numeric
            if any(
                k in c.lower()
                for k in [
                    "spend",
                    "meta",
                    "google",
                    "tiktok",
                    "youtube",
                    "facebook",
                    "search",
                    "media",
                    "tv",
                    "radio",
                ]
            )
            and c not in targets
        ]
        controls = [
            c
            for c in numeric
            if c not in targets + channels
            and any(
                k in c.lower()
                for k in ["discount", "price", "holiday", "promo", "season", "competitor", "macro"]
            )
        ]
        if missing:
            issues.append(
                Finding(
                    severity="warning",
                    code="MISSING_PERIODS",
                    message="Potential missing periods detected",
                    evidence={"count": len(missing)},
                    suggested_action="Validate continuity before modeling",
                )
            )
        candidate = bool(date_col and targets and channels and len(df) >= 52)
        return DatasetInspection(
            dataset_id=dataset_id,
            rows=len(df),
            frequency=freq,
            date_range={"start": start, "end": end},
            possible_targets=targets,
            possible_channels=channels,
            possible_controls=controls,
            missing_periods=missing,
            issues=issues,
            mmm_candidate=candidate,
        )

    def validate(
        self, dataset_id, date_column, target_column, channel_columns, control_columns, dims=None
    ) -> DatasetValidationResult:
        df = self.load(dataset_id)
        findings = validate_mmm_dataset(
            df,
            date_column,
            target_column,
            channel_columns,
            control_columns,
            dims=dims or [],
        )
        valid = not any(f.severity == "error" for f in findings)

        temporal_summary = None
        if date_column in df.columns:
            clean_dates = (
                pd.to_datetime(df[date_column], errors="coerce").dropna().sort_values().drop_duplicates()
            )
            if len(clean_dates) >= 3:
                deltas = clean_dates.diff().dropna().dt.days
                med = float(deltas.median())
                freq = (
                    "daily"
                    if med <= 1.5
                    else "weekly"
                    if med <= 8
                    else "monthly"
                    if med <= 35
                    else "irregular"
                )
                if freq in ("daily", "weekly"):
                    step = pd.Timedelta(days=round(med)) if freq == "weekly" else pd.Timedelta(days=1)
                    expected_index = pd.date_range(clean_dates.min(), clean_dates.max(), freq=step)
                    missing_dates = expected_index.difference(clean_dates)
                    temporal_summary = {
                        "frequency": freq,
                        "observed_periods": len(clean_dates),
                        "expected_periods": len(expected_index),
                        "missing_period_count": len(missing_dates),
                    }
                else:
                    temporal_summary = {
                        "frequency": freq,
                        "observed_periods": len(clean_dates),
                        "expected_periods": len(clean_dates),
                        "missing_period_count": 0,
                    }

        return DatasetValidationResult(
            dataset_id=dataset_id,
            findings=findings,
            valid_for_modeling=valid,
            temporal_summary=temporal_summary,
        )


