from __future__ import annotations

import hashlib
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from marketing_mcp.domain.datasets.validation import validate_mmm_dataset
from marketing_mcp.schemas.models import (
    DatasetInspection,
    DatasetRegistration,
    DatasetValidationResult,
    Finding,
)
from marketing_mcp.security import safe_source_path


def _utc():
    return datetime.now(UTC).isoformat()


class DatasetService:
    def __init__(self, metadata, data_dir: Path, max_dataset_mb: int = 100):
        self.metadata = metadata
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_dataset_mb * 1024 * 1024

    def register_file(self, source: Path, principal: Any = None) -> DatasetRegistration:
        source = safe_source_path(Path(source), self.max_bytes)
        raw = source.read_bytes()
        fp = hashlib.sha256(raw).hexdigest()
        dataset_id = f"dataset_{fp[:12]}"
        ext = source.suffix.lower()
        dest = self.data_dir / f"{dataset_id}{ext}"
        if not dest.exists():
            shutil.copy2(source, dest)
        df = self._read(dest)
        owner = principal.subject if principal is not None else "local"
        tenant_id = principal.tenant_id if principal is not None else None
        rec = DatasetRegistration(
            dataset_id=dataset_id,
            path=str(dest),
            fingerprint=fp,
            format=ext[1:],
            rows=len(df),
            created_at=_utc(),
            owner=owner,
            tenant_id=tenant_id,
        )
        self.metadata.put_dataset(rec.model_dump())
        return rec

    def _read(self, path: Path):
        return pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_parquet(path)

    def load(self, dataset_id: str):
        rec = self.metadata.get_dataset(dataset_id)
        return self._read(Path(rec["path"]))

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
    ):
        findings = validate_mmm_dataset(
            self.load(dataset_id),
            date_column,
            target_column,
            channel_columns,
            control_columns,
            dims=dims or [],
        )
        valid = not any(f.severity == "error" for f in findings)
        return DatasetValidationResult(
            dataset_id=dataset_id, findings=findings, valid_for_modeling=valid
        )
