"""
CLV Adapter — wraps PyMC-Marketing Customer Lifetime Value models.

Supports: BG/NBD (BetaGeoModel), GammaGamma, and Shifted Beta Geometric (sBG).

Phase 3 — v0.5.0
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import pandas as pd

from marketing_mcp.errors import DomainError


class CLVAdapter:
    """Thin adapter boundary for PyMC-Marketing CLV models.

    Follows the same thin-boundary principle as PyMCMarketingAdapter:
    only PyMC-Marketing computation crosses this boundary.
    """

    MODEL_MAP: ClassVar[dict[str, str]] = {
        "bg_nbd": "BetaGeoModel",
        "gamma_gamma": "GammaGammaModel",
        "shifted_beta_geo": "ShiftedBetaGeometricModelIndividual",
    }

    def __init__(self):
        try:
            import pymc_marketing.clv as clv_module

            self._clv = clv_module
            # Verify key classes are importable
            self.BetaGeoModel = clv_module.BetaGeoModel
            self.GammaGammaModel = clv_module.GammaGammaModel
            try:
                self.sBGModel = clv_module.ShiftedBetaGeometricModelIndividual
            except AttributeError:
                self.sBGModel = None
        except ImportError as e:
            raise DomainError(
                "DEPENDENCY_UNAVAILABLE",
                "pymc_marketing.clv is not available in this runtime",
                evidence={"dependency": "pymc-marketing>=1.0.0"},
                next_action="Install project dependencies with uv sync",
            ) from e

    def _get_model_class(self, model_type: str):
        if model_type == "bg_nbd":
            return self.BetaGeoModel
        elif model_type == "gamma_gamma":
            return self.GammaGammaModel
        elif model_type == "shifted_beta_geo":
            if self.sBGModel is None:
                raise DomainError(
                    "MODEL_UNAVAILABLE",
                    "ShiftedBetaGeometricModelIndividual is not available in this PyMC-Marketing version",
                    next_action="Use bg_nbd or gamma_gamma model types",
                )
            return self.sBGModel
        raise DomainError(
            "INVALID_CLV_MODEL_TYPE",
            f"Unknown CLV model type '{model_type}'",
            evidence={"requested": model_type, "supported": list(self.MODEL_MAP.keys())},
        )

    def fit(self, df: pd.DataFrame, config: dict, artifact: Path) -> Any:
        """Fit a CLV model on RFM data and persist to NetCDF.

        Args:
            df: RFM-format DataFrame.
            config: CLV model config dict (model_type, column names, sampler).
            artifact: Path to save the fitted model NetCDF.

        Returns:
            Fitted CLV model instance.
        """
        model_type = config.get("model_type", "bg_nbd")
        model_cls = self._get_model_class(model_type)

        sampler = config.get("sampler", {})

        try:
            model = model_cls(
                data=df,
                model_config={},
                sampler_config={
                    "draws": sampler.get("draws", 1000),
                    "tune": sampler.get("tune", 1000),
                    "chains": sampler.get("chains", 4),
                    "target_accept": sampler.get("target_accept", 0.9),
                    "random_seed": sampler.get("random_seed", 42),
                },
            )
            model.build_model()
            model.fit(
                draws=sampler.get("draws", 1000),
                tune=sampler.get("tune", 1000),
                chains=sampler.get("chains", 4),
                target_accept=sampler.get("target_accept", 0.9),
                random_seed=sampler.get("random_seed", 42),
            )
            artifact.parent.mkdir(parents=True, exist_ok=True)
            model.save(str(artifact))
            return model
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                "CLV_FIT_FAILED",
                f"CLV model fitting failed: {e}",
                evidence={"model_type": model_type, "error": str(e)[:500]},
                next_action="Check RFM data format and column mappings",
            ) from e

    def predict_clv(self, model, future_t: int, top_n: int | None) -> dict[str, Any]:
        """Return per-customer P(alive), expected purchases, and expected revenue.

        Args:
            model: Fitted CLV model instance.
            future_t: Number of future periods to forecast.
            top_n: If set, return only the top N customers by expected revenue.

        Returns:
            Dict with per-customer predictions and summary statistics.
        """
        try:
            # Expected number of future purchases
            expected_purchases = model.expected_num_purchases(
                data=model.data,
                future_t=future_t,
            )
            # P(alive) for each customer
            p_alive = model.expected_probability_alive(data=model.data)

            import numpy as np

            customers = (
                model.data[model.customer_id_col].tolist()
                if hasattr(model, "customer_id_col")
                else list(range(len(model.data)))
            )
            exp_purchases_arr = expected_purchases.values.flatten()
            p_alive_arr = p_alive.values.flatten()

            # Build per-customer records
            records = []
            for i, cust_id in enumerate(customers):
                records.append(
                    {
                        "customer_id": cust_id,
                        "p_alive": float(np.clip(p_alive_arr[i], 0.0, 1.0)),
                        "expected_purchases": float(max(0.0, exp_purchases_arr[i])),
                    }
                )

            # Sort by expected_purchases descending
            records.sort(key=lambda r: r["expected_purchases"], reverse=True)

            if top_n is not None:
                records = records[:top_n]

            return {
                "future_t": future_t,
                "total_customers": len(records),
                "customers": records,
                "summary": {
                    "mean_p_alive": float(np.mean([r["p_alive"] for r in records])),
                    "mean_expected_purchases": float(
                        np.mean([r["expected_purchases"] for r in records])
                    ),
                    "customers_likely_alive": int(sum(1 for r in records if r["p_alive"] >= 0.5)),
                },
            }
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                "CLV_PREDICT_FAILED",
                f"CLV prediction failed: {e}",
                evidence={"error": str(e)[:500]},
                next_action="Ensure the model was fitted successfully with valid RFM data",
            ) from e

    def churn_risk_cohorts(self, model, threshold_p_alive: float = 0.3) -> dict[str, Any]:
        """Identify customers below P(alive) threshold (churn risk).

        Args:
            model: Fitted CLV model (must support expected_probability_alive).
            threshold_p_alive: Customers with P(alive) < threshold are at-risk.

        Returns:
            Dict with at-risk customers and summary statistics.
        """
        try:
            import numpy as np

            p_alive = model.expected_probability_alive(data=model.data)
            customers = (
                model.data[model.customer_id_col].tolist()
                if hasattr(model, "customer_id_col")
                else list(range(len(model.data)))
            )
            p_alive_arr = p_alive.values.flatten()

            at_risk = []
            for i, cust_id in enumerate(customers):
                pa = float(np.clip(p_alive_arr[i], 0.0, 1.0))
                if pa < threshold_p_alive:
                    at_risk.append({"customer_id": cust_id, "p_alive": pa})

            at_risk.sort(key=lambda r: r["p_alive"])

            return {
                "threshold_p_alive": threshold_p_alive,
                "total_customers": len(customers),
                "at_risk_count": len(at_risk),
                "at_risk_pct": round(len(at_risk) / max(1, len(customers)) * 100, 2),
                "at_risk_customers": at_risk,
            }
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                "CLV_CHURN_FAILED",
                f"Churn risk computation failed: {e}",
                evidence={"error": str(e)[:500]},
                next_action="Ensure the model was fitted with a supported CLV model type",
            ) from e
