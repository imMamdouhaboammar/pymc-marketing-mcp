"""
Headless posterior visualization service for PyMC Marketing MCP.

Generates PNG/SVG plots from fitted MMM posterior samples using
ArviZ and PyMC-Marketing plotting APIs. All rendering is headless
(Agg backend) — no display required.

Phase 2 — v0.4.1
"""

from __future__ import annotations

import base64
import io
from dataclasses import asdict
from pathlib import Path
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.repositories.models import ArtifactRef
from marketing_mcp.storage.artifacts import LocalArtifactStore

# Supported plot types and their human-readable descriptions
SUPPORTED_PLOT_TYPES: dict[str, str] = {
    "saturation_curves": "Channel saturation/response curves with 94% HDI bands",
    "waterfall_decomposition": "Contribution waterfall decomposition by component",
    "actual_vs_predicted": "Actual target vs posterior predictive samples with HDI",
    "channel_contribution_share": "Channel contribution share distribution with 94% HDI",
}


class PlottingService:
    """Headless PNG/SVG plot generation from fitted MMM posteriors.

    Uses matplotlib Agg backend and ArviZ/PyMC-Marketing plotting APIs.
    Returns raw bytes (PNG/SVG). Never writes to temp disk — output
    is kept in-memory via BytesIO to avoid path traversal surface.
    """

    def __init__(
        self,
        artifact_storage: LocalArtifactStore | Path | None = None,
        *,
        metadata=None,
        artifacts_dir: Path | None = None,
        plots_dir: Path | None = None,
    ):
        storage = artifact_storage or artifacts_dir or plots_dir
        if storage is None:
            raise ValueError("artifact_storage, artifacts_dir, or plots_dir must be provided")
        self.artifacts = (
            storage
            if isinstance(storage, LocalArtifactStore)
            else LocalArtifactStore(storage)
        )
        self.metadata = metadata
        self.plots_dir = self.artifacts.root / "plots"
        self.plots_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_agg_backend()

    @staticmethod
    def _ensure_agg_backend() -> None:
        """Force headless Agg backend before any matplotlib import."""
        import matplotlib

        matplotlib.use("Agg")

    def generate_plot(
        self,
        model,
        model_id: str,
        plot_type: str,
        fmt: str = "png",
    ) -> bytes:
        """Generate a posterior plot and return raw bytes.

        Args:
            model: Loaded PyMC-Marketing MMM instance with idata.
            model_id: Model identifier for caching path.
            plot_type: One of SUPPORTED_PLOT_TYPES keys.
            fmt: Output format — 'png' or 'svg'.

        Returns:
            Raw image bytes in the requested format.

        Raises:
            DomainError: If plot_type is unknown or rendering fails.
        """
        from marketing_mcp.security import safe_identifier

        safe_identifier(model_id, "model")
        if fmt not in {"png", "svg"}:
            raise DomainError(
                "INVALID_PLOT_FORMAT",
                f"Unsupported plot format '{fmt}'. Must be 'png' or 'svg'.",
                evidence={"format": fmt},
            )

        if plot_type not in SUPPORTED_PLOT_TYPES:
            raise DomainError(
                "INVALID_PLOT_TYPE",
                f"Unknown plot type '{plot_type}'",
                evidence={
                    "requested": plot_type,
                    "supported": list(SUPPORTED_PLOT_TYPES.keys()),
                },
                next_action=f"Use one of: {', '.join(SUPPORTED_PLOT_TYPES.keys())}",
            )

        try:
            render_fn = getattr(self, f"_render_{plot_type}")
            img_bytes = render_fn(model, fmt)
        except DomainError:
            raise
        except Exception as e:
            msg = str(e)[:500]
            if plot_type == "actual_vs_predicted" or "posterior predictive" in msg.lower():
                next_action = "Ensure the model was fitted with posterior predictive samples."
            elif plot_type == "saturation_curves":
                next_action = "Check model saturation specifications or inspect get_response_curves."
            else:
                next_action = f"Review model diagnostic metrics or check parameters for plot type '{plot_type}'."
            raise DomainError(
                "PLOT_RENDER_FAILED",
                f"Failed to render plot '{plot_type}': {msg}",
                evidence={"type": type(e).__name__, "message": msg, "plot_type": plot_type},
                next_action=next_action,
            ) from e

        if self.metadata is not None:
            record = self.metadata.get_model(model_id)
            ref = self.artifacts.put_bytes(
                img_bytes,
                content_type="image/png" if fmt == "png" else "image/svg+xml",
                owner=record.get("owner") or "local",
                tenant_id=record.get("tenant_id"),
            )
            refs = dict(record.get("plot_refs") or {})
            refs[f"{plot_type}.{fmt}"] = asdict(ref)
            record["plot_refs"] = refs
            self.metadata.put_model(record)
        else:
            cache_dir = self.plots_dir / model_id
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / f"{plot_type}.{fmt}").write_bytes(img_bytes)

        return img_bytes

    def get_cached_plot(self, model_id: str, plot_type: str, fmt: str = "png") -> bytes | None:
        """Return cached plot bytes or None if not yet generated."""
        from marketing_mcp.security import safe_identifier

        safe_identifier(model_id, "model")
        if fmt not in {"png", "svg"}:
            return None
        if self.metadata is not None:
            try:
                record = self.metadata.get_model(model_id)
            except DomainError:
                return None
            raw_ref = (record.get("plot_refs") or {}).get(f"{plot_type}.{fmt}")
            if raw_ref is None:
                return None
            ref = ArtifactRef(**raw_ref)
            return self.artifacts.read_bytes(
                ref,
                owner=record.get("owner") or "local",
                tenant_id=record.get("tenant_id"),
            )
        cache_path = self.plots_dir / model_id / f"{plot_type}.{fmt}"
        return cache_path.read_bytes() if cache_path.exists() else None

    def generate_all(
        self,
        model,
        model_id: str,
        plot_types: list[str],
        fmt: str = "png",
    ) -> dict[str, Any]:
        """Generate multiple plots and return a summary dict."""
        results: dict[str, Any] = {}
        for pt in plot_types:
            try:
                img_bytes = self.generate_plot(model, model_id, pt, fmt)
                results[pt] = {
                    "success": True,
                    "size_bytes": len(img_bytes),
                    "data_b64": base64.b64encode(img_bytes).decode("ascii"),
                    "uri": f"marketing://models/{model_id}/plots/{pt}",
                    "description": SUPPORTED_PLOT_TYPES.get(pt, ""),
                }
            except DomainError as e:
                results[pt] = {
                    "success": False,
                    "error": e.to_dict().get("error", {}),
                }
        return results

    # ------------------------------------------------------------------
    # Private render methods — one per plot_type
    # ------------------------------------------------------------------

    def _render_saturation_curves(self, model, fmt: str) -> bytes:
        """Render channel saturation curves using PyMC-Marketing plot suite or fallback."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        fig = None

        # Strategy 1: Official model.plot.saturation_curves(curve=curve)
        if hasattr(model, "sample_saturation_curve") and hasattr(model, "plot") and model.plot is not None:
            try:
                curve = model.sample_saturation_curve(original_scale=False)
                if hasattr(model.plot, "saturation_curves"):
                    fig, _ = model.plot.saturation_curves(curve=curve)
            except Exception:
                fig = None

        # Strategy 2: Transformation plot_curve_hdi with correct axes kwarg
        if fig is None and hasattr(model, "sample_saturation_curve") and hasattr(model, "saturation") and hasattr(model.saturation, "plot_curve_hdi"):
            try:
                curve = model.sample_saturation_curve(original_scale=False)
                fig, ax = plt.subplots(figsize=(10, 5))
                axes_arr = np.array([[ax]])
                fig, _ = model.saturation.plot_curve_hdi(curve=curve, axes=axes_arr)
            except Exception:
                fig = None

        # Strategy 3: Parameter posterior histograms
        if fig is None:
            channels = getattr(model, "channel_columns", [])
            n_ch = max(1, len(channels))
            fig, axes = plt.subplots(
                1, n_ch, figsize=(4 * n_ch, 4)
            )
            if n_ch == 1:
                axes = [axes]
            idata = getattr(model, "idata", None)
            posterior = getattr(idata, "posterior", {}) if idata is not None else {}
            has_sat_plot = False
            for i, ch in enumerate(channels):
                if "saturation_lam" in posterior:
                    da = posterior["saturation_lam"]
                    if hasattr(da, "dims") and "channel" in da.dims:
                        vals = da.sel(channel=ch).values.flatten()
                        axes[i].hist(vals, bins=30, edgecolor="black", color="#4361ee", alpha=0.7)
                        axes[i].set_title(f"{ch}\n(saturation λ)")
                        has_sat_plot = True
                    else:
                        axes[i].text(0.5, 0.5, f"{ch}\nNo saturation posterior", ha="center")
                else:
                    axes[i].text(0.5, 0.5, f"{ch}\nNo saturation posterior", ha="center")

            if has_sat_plot:
                fig.suptitle("Channel Saturation Parameters — Posterior", fontsize=12)
            else:
                plt.close(fig)
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.text(
                    0.5,
                    0.5,
                    "Saturation curve API unavailable\nfor this model version",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
                ax.set_title("Saturation Curves")

        return self._fig_to_bytes(fig, fmt)

    def _render_waterfall_decomposition(self, model, fmt: str) -> bytes:
        """Render contribution waterfall using PyMC-Marketing API or ArviZ fallback."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        idata = model.idata

        # Try PyMC-Marketing native waterfall if available
        if hasattr(model, "plot") and model.plot is not None:
            try:
                plot_obj = model.plot
                if hasattr(plot_obj, "waterfall"):
                    fig = plot_obj.waterfall().get_figure()
                    return self._fig_to_bytes(fig, fmt)
            except (AttributeError, KeyError, ValueError, TypeError):
                pass  # fall through to manual waterfall

        # Manual waterfall from channel contributions
        fig, ax = plt.subplots(figsize=(10, 5))

        try:
            # Numerical aggregation lives in the tested domain layer: per-draw
            # time aggregation before cross-draw median.
            from marketing_mcp.domain.posterior_summaries import (
                summarize_channel_contributions,
            )

            summary = summarize_channel_contributions(idata)
            channel_names = [
                str(c) for c in np.asarray(summary["median"].coords["channel"]).tolist()
            ]
            medians = [
                float(summary["median"].sel(channel=ch).values) for ch in channel_names
            ]
        except DomainError:
            channel_names = []
            medians = []

        if channel_names:
            colors = plt.cm.tab10(range(len(channel_names)))  # type: ignore[call-overload]
            bars = ax.bar(channel_names, medians, color=colors)
            ax.bar_label(bars, fmt="%.0f", padding=3)
            ax.set_title("Channel Contribution Waterfall — Posterior Median")
            ax.set_ylabel("Contribution (original scale)")
            ax.tick_params(axis="x", rotation=30)
        else:
            ax.text(
                0.5,
                0.5,
                "Channel contribution variable not found\nin posterior",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("Contribution Waterfall")

        fig.tight_layout()
        return self._fig_to_bytes(fig, fmt)

    def _render_actual_vs_predicted(self, model, fmt: str) -> bytes:
        """Render actual observations vs posterior predictive with HDI."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        idata = model.idata
        fig, ax = plt.subplots(figsize=(12, 4))

        try:
            # Time dimension identified by name/coordinate in the domain layer.
            from marketing_mcp.domain.posterior_summaries import summarize_predictions

            summary = summarize_predictions(idata)
            time_coord = next(
                (d for d in summary.dims if d in ("date", "date_week", "week", "time", "period")),
                None,
            )
            if time_coord is None:
                raise DomainError("DATA_INVALID", "No time dimension in prediction summary")

            median = np.asarray(summary["median"].values)
            lower = np.asarray(summary["lower"].values)
            upper = np.asarray(summary["upper"].values)
            t = (
                np.asarray(summary[time_coord].values)
                if time_coord in summary.coords
                else np.arange(median.shape[0])
            )

            obs_group = idata.get("observed_data")
            obs_ds = getattr(obs_group, "dataset", None) or obs_group
            obs_var = (
                next((v for v in obs_ds.data_vars), None)
                if obs_ds is not None and hasattr(obs_ds, "data_vars")
                else None
            )
            if obs_ds is not None and obs_var is not None:
                ax.fill_between(t, lower, upper, alpha=0.3, label="94% HDI")
                ax.plot(t, median, label="Predicted median", linewidth=1.5)
                ax.plot(
                    t,
                    np.asarray(obs_ds[obs_var].values).reshape(-1),
                    "k.",
                    alpha=0.7,
                    markersize=3,
                    label="Observed",
                )
                ax.set_title("Actual vs Posterior Predictive")
                ax.set_xlabel("Time period")
                ax.legend(fontsize=8)
            else:
                ax.text(
                    0.5,
                    0.5,
                    "Observed data variable not found",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
        except DomainError as exc:
            ax.text(
                0.5,
                0.5,
                f"No posterior predictive samples found.\n{exc.message}",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            ax.set_title("Actual vs Predicted")

        fig.tight_layout()
        return self._fig_to_bytes(fig, fmt)

    def _render_channel_contribution_share(self, model, fmt: str) -> bytes:
        """Render channel contribution share as a pie/bar with uncertainty."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np

        idata = model.idata
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        try:
            # Per-draw aggregation before cross-draw summary (domain layer).
            from marketing_mcp.domain.posterior_summaries import (
                summarize_channel_contributions,
            )

            summary = summarize_channel_contributions(idata)
            channel_names = [
                str(c) for c in np.asarray(summary["median"].coords["channel"]).tolist()
            ]
            medians = [
                float(summary["median"].sel(channel=ch).values) for ch in channel_names
            ]
            lower_95s = [
                float(summary["lower"].sel(channel=ch).values) for ch in channel_names
            ]
            upper_95s = [
                float(summary["upper"].sel(channel=ch).values) for ch in channel_names
            ]
            has_data = bool(channel_names)
        except DomainError:
            channel_names = []
            medians = []
            has_data = False

        if has_data:

            total = sum(medians) if sum(medians) > 0 else 1.0
            shares = [m / total * 100 for m in medians]

            # Bar chart with error bars
            colors = plt.cm.tab10(range(len(channel_names)))  # type: ignore[call-overload]
            y_pos = np.arange(len(channel_names))
            # Error bars from the same per-draw summary (94% interval), scaled
            # into share space so the chart carries its own uncertainty.
            denom = total
            yerr_lower = [(m - lo) / denom * 100 for m, lo in zip(medians, lower_95s)]
            yerr_upper = [(up - m) / denom * 100 for m, up in zip(medians, upper_95s)]
            axes[0].barh(
                y_pos,
                shares,
                color=colors,
                xerr=[yerr_lower, yerr_upper],
                ecolor="gray",
                capsize=3,
            )
            axes[0].set_yticks(y_pos)
            axes[0].set_yticklabels(channel_names)
            axes[0].set_xlabel("Contribution share (%)")
            axes[0].set_title("Channel Contribution Share\n(Posterior Median)")

            # Pie chart
            axes[1].pie(
                shares, labels=channel_names, autopct="%1.1f%%", colors=colors, startangle=90
            )
            axes[1].set_title("Contribution Share Breakdown")
        else:
            for ax in axes:
                ax.text(
                    0.5,
                    0.5,
                    "Channel contribution variable\nnot found in posterior",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )

        fig.suptitle("Channel Contribution Share — Posterior Median", y=1.02)
        fig.tight_layout()
        return self._fig_to_bytes(fig, fmt)

    @staticmethod
    def _fig_to_bytes(fig, fmt: str) -> bytes:
        """Save matplotlib figure to bytes and close it."""
        import matplotlib.pyplot as plt

        buf = io.BytesIO()
        try:
            fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=150)
            buf.seek(0)
            return buf.read()
        finally:
            plt.close(fig)
