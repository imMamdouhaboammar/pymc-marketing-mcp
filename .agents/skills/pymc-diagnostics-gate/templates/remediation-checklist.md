# Diagnostic Remediation Checklist

Use this checklist when a model receives `decision_status: "rejected"` or `decision_status: "caution"`.

## 1. Diagnosis Summary
- **Model ID**: `[model_id]`
- **Divergences**: `[count]` (Must be 0 for full approval)
- **Max R-hat**: `[max_rhat]` (Must be $\le 1.05$; target $\le 1.01$)
- **Min Bulk ESS**: `[min_ess]` (Target $\ge 400$)

## 2. Remediation Protocol
1. **If Divergences Present**:
   - Elevate `target_accept` from 0.90 to 0.95 or 0.98.
   - Increase warmup iterations (`tune`) to 2000.
2. **If Elevated R-hat ($> 1.01$)**:
   - For cautionary R-hat ($1.01 < \hat{R} \le 1.05$): examine parameter traces, consider increasing `draws` and `tune` for better chain mixing, and verify that prior distributions are not overly diffuse.
   - For severe non-convergence ($\hat{R} > 1.05$): check channel correlations for near-perfect collinearity, increase `draws` and `tune`, re-evaluate prior plausibility, and simplify saturation or adstock parameterization.
3. **If Low ESS ($< 400$)**:
   - Autocorrelation is high. Verify adstock lag lengths are not excessively long.
   - Increase total draws.

## 3. Verification Step
- Execute `diagnose_mmm(model_id=new_model_id)` on the refitted model.
- Confirm `decision_status == "approved"` before proceeding to decision tools.
