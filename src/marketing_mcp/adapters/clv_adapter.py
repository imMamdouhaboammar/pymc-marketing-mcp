"""CLV Adapter — wraps PyMC-Marketing Customer Lifetime Value models.

Supports: BG/NBD (BetaGeoModel), GammaGamma (GammaGammaModel), and Shifted Beta Geometric (ShiftedBetaGeoModel).
Ensures data column normalization into canonical schemas, model-specific separation,
and accurate total customer population reporting across all endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from marketing_mcp.errors import DomainError


class CLVAdapter:
    """Thin adapter boundary for PyMC-Marketing CLV models."""

    MODEL_MAP: ClassVar[dict[str, str]] = {
        "bg_nbd": "BetaGeoModel",
        "gamma_gamma": "GammaGammaModel",
        "shifted_beta_geo": "ShiftedBetaGeoModel",
    }

    def __init__(self):
        try:
            import pymc_marketing.clv as clv_module

            self._clv = clv_module
            self.BetaGeoModel = clv_module.BetaGeoModel
            self.GammaGammaModel = clv_module.GammaGammaModel
            self.ShiftedBetaGeoModel = getattr(clv_module, "ShiftedBetaGeoModel", None)
            if self.ShiftedBetaGeoModel is None:
                self.ShiftedBetaGeoModel = getattr(
                    clv_module, "ShiftedBetaGeometricModelIndividual", None
                )
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
            if self.ShiftedBetaGeoModel is None:
                raise DomainError(
                    "MODEL_UNAVAILABLE",
                    "ShiftedBetaGeoModel is not available in this PyMC-Marketing version",
                    next_action="Use bg_nbd or gamma_gamma model types",
                )
            return self.ShiftedBetaGeoModel
        raise DomainError(
            "INVALID_CLV_MODEL_TYPE",
            f"Unknown CLV model type '{model_type}'",
            evidence={"requested": model_type, "supported": list(self.MODEL_MAP.keys())},
        )

    def normalize_data(self, df: pd.DataFrame, model_type: str, config: dict[str, Any]) -> pd.DataFrame:
        """Normalize arbitrary user column names into canonical DataFrame expected by the model."""
        cust_col = config.get("customer_id_col") or config.get("customer_id_column") or "customer_id"
        freq_col = config.get("frequency_col") or config.get("frequency_column") or "frequency"
        rec_col = config.get("recency_col") or config.get("recency_column") or "recency"
        t_col = config.get("T_col") or config.get("T_column") or "T"
        mon_col = config.get("monetary_value_col") or config.get("monetary_value_column") or "monetary_value"
        cohort_col = config.get("cohort_col") or config.get("cohort_column") or "cohort"

        if cust_col not in df.columns:
            raise DomainError(
                "MISSING_RFM_COLUMNS",
                f"Customer identifier column '{cust_col}' missing from dataset",
                evidence={"missing": [cust_col], "available": list(df.columns)},
            )

        if df[cust_col].duplicated().any():
            n_dup = int(df[cust_col].duplicated().sum())
            raise DomainError(
                "DUPLICATE_CUSTOMER_IDS",
                f"Customer column '{cust_col}' has {n_dup} duplicate entries",
                evidence={"column": cust_col, "duplicate_count": n_dup},
                next_action="Aggregate to one row per customer before fitting CLV",
            )

        if model_type == "bg_nbd":
            for col_name, label in [(freq_col, "frequency"), (rec_col, "recency"), (t_col, "T")]:
                if col_name not in df.columns:
                    raise DomainError(
                        "MISSING_RFM_COLUMNS",
                        f"Required BG/NBD column '{col_name}' ({label}) missing from dataset",
                        evidence={"missing": [col_name], "available": list(df.columns)},
                    )
                if (df[col_name] < 0).any():
                    raise DomainError(
                        "INVALID_RFM_DATA",
                        f"Column '{col_name}' contains negative values — RFM values must be non-negative",
                        evidence={"column": col_name, "min_value": float(df[col_name].min())},
                    )

            out_df = pd.DataFrame(
                {
                    "customer_id": df[cust_col],
                    "frequency": df[freq_col],
                    "recency": df[rec_col],
                    "T": df[t_col],
                }
            )
            return out_df

        elif model_type == "gamma_gamma":
            for col_name, label in [(freq_col, "frequency"), (mon_col, "monetary_value")]:
                if col_name not in df.columns:
                    raise DomainError(
                        "MISSING_RFM_COLUMNS",
                        f"Required Gamma-Gamma column '{col_name}' ({label}) missing from dataset",
                        evidence={"missing": [col_name], "available": list(df.columns)},
                    )
                if (df[col_name] < 0).any():
                    raise DomainError(
                        "INVALID_RFM_DATA",
                        f"Column '{col_name}' contains negative values",
                        evidence={"column": col_name},
                    )

            # Gamma-Gamma requires repeat transactions (frequency > 0)
            repeat_mask = df[freq_col] > 0
            if not repeat_mask.any():
                raise DomainError(
                    "INVALID_RFM_DATA",
                    "Gamma-Gamma model requires at least one customer with repeat purchases (frequency > 0)",
                    evidence={"repeat_customer_count": 0},
                )
            out_df = pd.DataFrame(
                {
                    "customer_id": df.loc[repeat_mask, cust_col],
                    "frequency": df.loc[repeat_mask, freq_col],
                    "monetary_value": df.loc[repeat_mask, mon_col],
                }
            ).reset_index(drop=True)
            return out_df

        elif model_type == "shifted_beta_geo":
            for col_name, label in [(rec_col, "recency"), (t_col, "T"), (cohort_col, "cohort")]:
                if col_name not in df.columns:
                    raise DomainError(
                        "MISSING_RFM_COLUMNS",
                        f"Required Shifted-Beta-Geometric column '{col_name}' ({label}) missing from dataset",
                        evidence={"missing": [col_name], "available": list(df.columns)},
                    )
            out_df = pd.DataFrame(
                {
                    "customer_id": df[cust_col],
                    "recency": df[rec_col],
                    "T": df[t_col],
                    "cohort": df[cohort_col],
                }
            )
            return out_df

        raise DomainError("INVALID_CLV_MODEL_TYPE", f"Unknown model type '{model_type}'")

    def fit(self, df: pd.DataFrame, config: dict, artifact: Path) -> Any:
        """Fit a CLV model on normalized data and persist to NetCDF."""
        model_type = config.get("model_type", "bg_nbd")
        model_cls = self._get_model_class(model_type)
        normalized_df = self.normalize_data(df, model_type, config)

        sampler = config.get("sampler", {})
        draws = sampler.get("draws", 1000)
        tune = sampler.get("tune", 1000)
        chains = sampler.get("chains", 4)
        target_accept = sampler.get("target_accept", 0.9)
        random_seed = sampler.get("random_seed", 42)

        try:
            model = model_cls(
                model_config={},
                sampler_config={
                    "draws": draws,
                    "tune": tune,
                    "chains": chains,
                    "target_accept": target_accept,
                    "random_seed": random_seed,
                },
            )
            model.fit(
                data=normalized_df,
                draws=draws,
                tune=tune,
                chains=chains,
                target_accept=target_accept,
                random_seed=random_seed,
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

    def predict_expected_purchases(
        self,
        model: Any,
        data: pd.DataFrame | None = None,
        future_t: int = 12,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        """Generate expected future purchases from a fitted BG/NBD model."""
        eval_data = data if data is not None else getattr(model, "data", None)
        if eval_data is None:
            raise DomainError("INPUT_INVALID", "No dataset available for purchase prediction")

        try:
            res_xr = model.expected_purchases(data=eval_data, future_t=future_t)
            # Reduce posterior draws to mean point estimate
            point_estimates = res_xr.mean(dim=["chain", "draw"]).values.flatten()
            cust_ids = eval_data["customer_id"].tolist()

            total_population = len(cust_ids)
            records = []
            for cid, ep in zip(cust_ids, point_estimates, strict=False):
                records.append(
                    {
                        "customer_id": cid,
                        "expected_purchases": float(max(0.0, float(ep))),
                    }
                )

            records.sort(key=lambda r: r["expected_purchases"], reverse=True)
            all_ep = [r["expected_purchases"] for r in records]

            output_records = records[:top_n] if top_n is not None else records

            return {
                "future_t": future_t,
                "total_customers": total_population,
                "returned_customers": len(output_records),
                "customers": output_records,
                "summary": {
                    "mean_expected_purchases": float(np.mean(all_ep)) if all_ep else 0.0,
                    "total_expected_purchases": float(np.sum(all_ep)) if all_ep else 0.0,
                    "max_expected_purchases": float(np.max(all_ep)) if all_ep else 0.0,
                },
            }
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                "CLV_PREDICT_FAILED",
                f"Expected purchases prediction failed: {e}",
                evidence={"error": str(e)[:500]},
            ) from e

    def predict_probability_alive(
        self,
        model: Any,
        data: pd.DataFrame | None = None,
        future_t: int = 0,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        """Generate Bayesian probability of customer alive from a fitted purchase or churn model."""
        eval_data = data if data is not None else getattr(model, "data", None)
        if eval_data is None:
            raise DomainError("INPUT_INVALID", "No dataset available for probability alive prediction")

        try:
            # ShiftedBetaGeoModel requires future_t argument in expected_probability_alive
            if hasattr(model, "expected_probability_alive"):
                try:
                    res_xr = model.expected_probability_alive(data=eval_data, future_t=future_t)
                except TypeError:
                    res_xr = model.expected_probability_alive(data=eval_data)
            else:
                raise DomainError("UNSUPPORTED_OPERATION", "Model does not support expected_probability_alive")

            point_estimates = res_xr.mean(dim=["chain", "draw"]).values.flatten()
            cust_ids = eval_data["customer_id"].tolist()

            total_population = len(cust_ids)
            records = []
            for cid, pa in zip(cust_ids, point_estimates, strict=False):
                records.append(
                    {
                        "customer_id": cid,
                        "p_alive": float(np.clip(float(pa), 0.0, 1.0)),
                    }
                )

            records.sort(key=lambda r: r["p_alive"], reverse=True)
            all_pa = [r["p_alive"] for r in records]

            output_records = records[:top_n] if top_n is not None else records

            return {
                "total_customers": total_population,
                "returned_customers": len(output_records),
                "customers": output_records,
                "summary": {
                    "mean_p_alive": float(np.mean(all_pa)) if all_pa else 0.0,
                    "customers_likely_alive": int(sum(1 for p in all_pa if p >= 0.5)),
                    "customers_at_churn_risk": int(sum(1 for p in all_pa if p < 0.3)),
                },
            }
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                "CLV_PREDICT_FAILED",
                f"Probability alive prediction failed: {e}",
                evidence={"error": str(e)[:500]},
            ) from e

    def predict_expected_spend(
        self,
        model: Any,
        data: pd.DataFrame | None = None,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        """Generate expected transaction spend per customer from a fitted Gamma-Gamma model."""
        eval_data = data if data is not None else getattr(model, "data", None)
        if eval_data is None:
            raise DomainError("INPUT_INVALID", "No dataset available for spend prediction")

        try:
            res_xr = model.expected_customer_spend(data=eval_data)
            point_estimates = res_xr.mean(dim=["chain", "draw"]).values.flatten()
            cust_ids = eval_data["customer_id"].tolist()

            total_population = len(cust_ids)
            records = []
            for cid, es in zip(cust_ids, point_estimates, strict=False):
                records.append(
                    {
                        "customer_id": cid,
                        "expected_spend": float(max(0.0, float(es))),
                    }
                )

            records.sort(key=lambda r: r["expected_spend"], reverse=True)
            all_spend = [r["expected_spend"] for r in records]

            output_records = records[:top_n] if top_n is not None else records

            return {
                "total_customers": total_population,
                "returned_customers": len(output_records),
                "customers": output_records,
                "summary": {
                    "mean_expected_spend": float(np.mean(all_spend)) if all_spend else 0.0,
                    "median_expected_spend": float(np.median(all_spend)) if all_spend else 0.0,
                },
            }
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                "CLV_PREDICT_FAILED",
                f"Expected customer spend prediction failed: {e}",
                evidence={"error": str(e)[:500]},
            ) from e

    def estimate_customer_lifetime_value(
        self,
        purchase_model: Any,
        value_model: Any,
        data: pd.DataFrame | None = None,
        future_t: int = 12,
        discount_rate: float = 0.0,
        top_n: int | None = None,
    ) -> dict[str, Any]:
        """Estimate combined discounted CLV using a purchase model and value model."""
        if data is not None:
            eval_data = data
        else:
            p_df = getattr(purchase_model, "data", None)
            v_df = getattr(value_model, "data", None)
            if p_df is not None and v_df is not None:
                eval_data = pd.merge(
                    p_df,
                    v_df[["customer_id", "monetary_value"]],
                    on="customer_id",
                    how="inner",
                )
            elif v_df is not None:
                eval_data = v_df
            else:
                eval_data = p_df

        if eval_data is None or len(eval_data) == 0:
            raise DomainError("INPUT_INVALID", "No dataset available for combined CLV estimation")

        try:
            # Call PyMC-Marketing Gamma-Gamma CLV method
            data_clean = eval_data.copy()
            res_xr = value_model.expected_customer_lifetime_value(
                transaction_model=purchase_model,
                data=data_clean,
                future_t=future_t,
                discount_rate=discount_rate,
            )
            point_estimates = res_xr.mean(dim=["chain", "draw"]).values.flatten()
            cust_ids = eval_data["customer_id"].tolist()

            total_population = len(cust_ids)
            records = []
            for cid, clv_val in zip(cust_ids, point_estimates, strict=False):
                records.append(
                    {
                        "customer_id": cid,
                        "clv": float(max(0.0, float(clv_val))),
                    }
                )

            records.sort(key=lambda r: r["clv"], reverse=True)
            all_clv = [r["clv"] for r in records]

            output_records = records[:top_n] if top_n is not None else records

            return {
                "future_t": future_t,
                "discount_rate": discount_rate,
                "total_customers": total_population,
                "returned_customers": len(output_records),
                "customers": output_records,
                "summary": {
                    "mean_clv": float(np.mean(all_clv)) if all_clv else 0.0,
                    "total_portfolio_clv": float(np.sum(all_clv)) if all_clv else 0.0,
                    "median_clv": float(np.median(all_clv)) if all_clv else 0.0,
                },
            }
        except DomainError:
            raise
        except Exception as e:
            raise DomainError(
                "CLV_PREDICT_FAILED",
                f"Combined CLV estimation failed: {e}",
                evidence={"error": str(e)[:500]},
            ) from e

    def churn_risk_cohorts(
        self,
        model: Any,
        data: pd.DataFrame | None = None,
        threshold_p_alive: float = 0.3,
    ) -> dict[str, Any]:
        """Identify customers below P(alive) threshold (churn risk)."""
        res = self.predict_probability_alive(model, data=data, top_n=None)
        total_customers = res["total_customers"]
        at_risk = [c for c in res["customers"] if c["p_alive"] < threshold_p_alive]
        at_risk.sort(key=lambda r: r["p_alive"])

        return {
            "threshold_p_alive": threshold_p_alive,
            "total_customers": total_customers,
            "at_risk_count": len(at_risk),
            "at_risk_pct": round(len(at_risk) / max(1, total_customers) * 100, 2),
            "at_risk_customers": at_risk,
        }

    def predict_clv(self, model: Any, future_t: int, top_n: int | None) -> dict[str, Any]:
        """Legacy compatibility method returning per-customer P(alive) and expected purchases."""
        p_res = self.predict_expected_purchases(model, future_t=future_t, top_n=None)
        a_res = self.predict_probability_alive(model, top_n=None)

        pa_map = {c["customer_id"]: c["p_alive"] for c in a_res["customers"]}
        combined = []
        for c in p_res["customers"]:
            cid = c["customer_id"]
            combined.append(
                {
                    "customer_id": cid,
                    "p_alive": pa_map.get(cid, 1.0),
                    "expected_purchases": c["expected_purchases"],
                }
            )

        total_customers = p_res["total_customers"]
        output_records = combined[:top_n] if top_n is not None else combined

        return {
            "future_t": future_t,
            "total_customers": total_customers,
            "returned_customers": len(output_records),
            "customers": output_records,
            "summary": {
                "mean_p_alive": a_res["summary"]["mean_p_alive"],
                "mean_expected_purchases": p_res["summary"]["mean_expected_purchases"],
                "customers_likely_alive": a_res["summary"]["customers_likely_alive"],
            },
        }
