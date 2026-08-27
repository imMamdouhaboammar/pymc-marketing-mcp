# Diagnostic Remediation Checklist

Use this checklist when a model receives `decision_status: "rejected"` or `decision_status: "approved_with_caution"`.

## 1. Diagnosis Summary
- **Model ID**: `mmm_rejected_v1`
- **Reported Failures**:
  - [x] Divergences $> 0$ (Observed: 14 divergences)
  - [ ] $\hat{R} > 1.05$ (Observed: 1.008)
  - [ ] Min Bulk ESS $< 50$ (Observed: 540)
  - [ ] Coverage $< 50\%$ (Observed: 88.5%)

## 2. Remediation Actions
1. **Sampler Reconfiguration**:
   - `target_accept`: Increase from `0.90` to `0.95`.
   - `tune`: Increase from `1000` to `2000`.
   - `draws`: Maintain `1000` per chain across 4 chains.
2. **Prior Adjustments**:
   - Channel: `tv_spend`
   - Action: Replace wide `hill` saturation with regularized `logistic` saturation.

## 3. Remediation Refit Input Payload
```json
{
  "dataset_id": "ds_ecommerce_2026",
  "date_column": "date",
  "target_column": "revenue",
  "channel_columns": ["meta_spend", "search_spend", "tv_spend"],
  "control_columns": ["promo_flag"],
  "yearly_seasonality": 2,
  "adstock": {"type": "geometric", "l_max": 8},
  "saturation": {"type": "logistic"},
  "channel_priors": {
    "tv_spend": {
      "adstock": {"type": "delayed", "l_max": 12},
      "saturation": {"type": "logistic"}
    }
  },
  "sampler": {
    "draws": 1000,
    "tune": 2000,
    "chains": 4,
    "target_accept": 0.95,
    "random_seed": 101
  }
}
```

## 4. Re-Diagnosis Verification
- New Model ID: `mmm_remediated_v2`
- Re-run `diagnose_mmm(model_id="mmm_remediated_v2")`
- Confirm `decision_status == "approved"` before proceeding to decision tools.
