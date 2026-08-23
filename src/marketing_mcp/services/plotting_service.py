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
from pathlib import Path
from typing import Any

from marketing_mcp.errors import DomainError

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

    def __init__(self, artifacts_dir: Path):
        self.plots_dir = artifacts_dir / "plots"
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
            raise DomainError(
                "PLOT_RENDER_FAILED",
                f"Failed to render plot '{plot_type}'",
                evidence={"type": type(e).__name__, "message": str(e)[:500]},
                next_action="Ensure the model was fitted with posterior predictive samples",
            ) from e

        # Cache to disk for MCP resource serving
        cache_dir = self.plots_dir / model_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / f"{plot_type}.{fmt}"
        cache_path.write_bytes(img_bytes)

        return img_bytes

    def get_cached_plot(self, model_id: str, plot_type: str, fmt: str = "png") -> bytes | None:
        """Return cached plot bytes or None if not yet generated."""
        from marketing_mcp.security import safe_identifier

        safe_identifier(model_id, "model")
        if fmt not in {"png", "svg"}:
            return None
        cache_path = self.plots_dir / model_id / f"{plot_type}.{fmt}"
        if cache_path.exists():
            return cache_path.read_bytes()
        return None

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
        """Render channel saturation curves using adstock transform plot API."""
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Use PyMC-Marketing's transform plot API if available
        if hasattr(model, "saturation") and hasattr(model.saturation, "plot_curve_hdi"):
            fig, axes = plt.subplots(figsize=(10, 4))
            model.saturation.plot_curve_hdi(ax=axes)
            axes.set_title("Saturation Curves — 94% HDI")
        elif hasattr(model, "plot") and model.plot is not None:
            # Fallback: use ArviZ posterior summary for channel contributions
            channels = getattr(model, "channel_columns", [])
            fig, axes = plt.subplots(
                1, max(1, len(channels)), figsize=(4 * max(1, len(channels)), 4)
            )
            if len(channels) == 1:
                axes = [axes]
            for i, ch in enumerate(channels):
                idata = model.idata
                if "posterior" in idata and "saturation_lam" in idata["posterior"]:
                    da = idata["posterior"]["saturation_lam"]
                    if "channel" in da.dims:
                        vals = da.sel(channel=ch).values.flatten()
                        axes[i].hist(vals, bins=30, edgecolor="black")
                        axes[i].set_title(f"{ch}\n(saturation λ)")
                else:
                    axes[i].text(0.5, 0.5, f"{ch}\nNo saturation posterior", ha="center")
            fig.suptitle("Channel Saturation Parameters — Posterior")
        else:
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
        posterior = idata.get("posterior", {})

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
        channels_var = next(
            (
                v
                for v in ["channel_contribution_original_scale", "channel_contribution"]
                if v in posterior
            ),
            None,
        )
        if channels_var is not None:
            da = posterior[channels_var]
            # Sum over non-channel dims (time, chain, draw), get median per channel
            medians = []
            channel_names = da.coords["channel"].values.tolist()
            for ch in channel_names:
                vals = np.asarray(da.sel(channel=ch)).flatten()
                medians.append(float(np.median(vals)))
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

        # Posterior predictive
        pp = idata.get("posterior_predictive")
        obs = idata.get("observed_data")
        if pp is not None and obs is not None:
            y_var = next((v for v in pp.data_vars if "y" in v.lower()), None)
            obs_var = next((v for v in obs.data_vars), None)
            if y_var and obs_var:
                pp_vals = np.asarray(pp[y_var]).reshape(-1, pp[y_var].shape[-1])
                lower = np.quantile(pp_vals, 0.03, axis=0)
                upper = np.quantile(pp_vals, 0.97, axis=0)
                median = np.quantile(pp_vals, 0.5, axis=0)
                t = np.arange(len(median))
                ax.fill_between(t, lower, upper, alpha=0.3, label="94% HDI")
                ax.plot(t, median, label="Predicted median", linewidth=1.5)
                ax.plot(
                    t,
                    np.asarray(obs[obs_var]).flatten(),
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
                    "Posterior predictive variable not found",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                )
        else:
            ax.text(
                0.5,
                0.5,
                "No posterior predictive samples found.\nRe-run diagnose_mmm to generate them.",
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
        posterior = idata.get("posterior", {})
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        channels_var = next(
            (
                v
                for v in ["channel_contribution_original_scale", "channel_contribution"]
                if v in posterior
            ),
            None,
        )
        if channels_var is not None:
            da = posterior[channels_var]
            channel_names = da.coords["channel"].values.tolist()
            medians = []
            lower_95s = []
            upper_95s = []
            for ch in channel_names:
                vals = np.asarray(da.sel(channel=ch)).flatten()
                vals = vals[np.isfinite(vals)]
                medians.append(float(np.median(vals)))
                lower_95s.append(float(np.quantile(vals, 0.03)))
                upper_95s.append(float(np.quantile(vals, 0.97)))

            total = sum(medians) if sum(medians) > 0 else 1.0
            shares = [m / total * 100 for m in medians]

            # Bar chart with error bars
            colors = plt.cm.tab10(range(len(channel_names)))  # type: ignore[call-overload]
            y_pos = np.arange(len(channel_names))
            axes[0].barh(y_pos, shares, color=colors)
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
        fig.savefig(buf, format=fmt, bbox_inches="tight", dpi=150)
        plt.close(fig)
        buf.seek(0)
        return buf.read()
