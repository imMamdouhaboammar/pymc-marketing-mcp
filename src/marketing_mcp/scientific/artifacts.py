"""Canonical MMM visual artifact generation and manifest creation (UP-059).

Generates waterfall, saturation, and channel contribution plots saved as
immutable artifacts with SHA-256 manifests conforming to the platform contract.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from marketing_mcp.services.plotting_service import PlottingService

SUPPORTED_ARTIFACT_KINDS = [
    "waterfall_plot",
    "adstock_plot",
    "channel_contributions",
]

PLOT_TYPE_MAPPING = {
    "waterfall_plot": "waterfall_decomposition",
    "adstock_plot": "saturation_curves",
    "channel_contributions": "channel_contribution_share",
}


class ArtifactManifest(BaseModel):
    """Canonical artifact manifest matching packages/contracts/schemas/artifact.json."""

    schema_version: str = "1.0"
    artifact_id: UUID = Field(default_factory=uuid4)
    organization_id: UUID
    project_id: UUID
    run_id: UUID
    kind: Literal[
        "trace_nc",
        "posterior_predictive",
        "diagnostic_report",
        "waterfall_plot",
        "adstock_plot",
        "channel_contributions",
        "pdf_report",
    ]
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    storage_uri: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    producer_service: str = "analytics-worker"
    producer_version: str = "0.1.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


def generate_mmm_artifacts(
    model: Any,
    run_id: UUID | str,
    organization_id: UUID | str,
    project_id: UUID | str,
    output_dir: Path | str,
    fmt: str = "png",
    kinds: list[str] | None = None,
    producer_service: str = "analytics-worker",
    producer_version: str = "0.1.0",
) -> list[ArtifactManifest]:
    """Render canonical MMM visual artifacts (waterfall, adstock, contributions).

    Args:
        model: Fitted PyMC-Marketing MMM model with idata.
        run_id: Execution run UUID.
        organization_id: Multi-tenant organization UUID.
        project_id: Project UUID.
        output_dir: Target directory on disk to write artifacts and manifest.json.
        fmt: Output format ('png' or 'svg'). Defaults to 'png'.
        kinds: Subset of SUPPORTED_ARTIFACT_KINDS to generate, or None for all.
        producer_service: Name of producing service. Defaults to 'analytics-worker'.
        producer_version: Version of producing service. Defaults to '0.1.0'.

    Returns:
        List of generated ArtifactManifest instances.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    org_uuid = UUID(str(organization_id))
    proj_uuid = UUID(str(project_id))
    run_uuid = UUID(str(run_id))

    selected_kinds = kinds if kinds is not None else list(SUPPORTED_ARTIFACT_KINDS)
    media_type = "image/png" if fmt == "png" else "image/svg+xml"

    # Headless rendering via PlottingService
    plotting_service = PlottingService(plots_dir=out_path)

    manifests: list[ArtifactManifest] = []

    for kind in selected_kinds:
        if kind not in SUPPORTED_ARTIFACT_KINDS:
            continue

        plot_type = PLOT_TYPE_MAPPING[kind]
        img_bytes = plotting_service.generate_plot(
            model=model,
            model_id=str(run_uuid),
            plot_type=plot_type,
            fmt=fmt,
        )

        artifact_file = out_path / f"{kind}.{fmt}"
        artifact_file.write_bytes(img_bytes)

        sha256_hash = hashlib.sha256(img_bytes).hexdigest()
        size_bytes = len(img_bytes)
        storage_uri = f"file://{artifact_file.resolve()}"

        manifest = ArtifactManifest(
            artifact_id=uuid4(),
            organization_id=org_uuid,
            project_id=proj_uuid,
            run_id=run_uuid,
            kind=kind,  # type: ignore[arg-type]
            media_type=media_type,
            size_bytes=size_bytes,
            sha256=sha256_hash,
            storage_uri=storage_uri,
            producer_service=producer_service,
            producer_version=producer_version,
            metadata={"format": fmt, "plot_type": plot_type},
        )
        manifests.append(manifest)

    # Write manifest.json
    manifest_path = out_path / "manifest.json"
    manifest_data = [m.model_dump(mode="json") for m in manifests]
    manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    return manifests
