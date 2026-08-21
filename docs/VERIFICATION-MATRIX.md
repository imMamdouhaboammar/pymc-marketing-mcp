# Statistical & Functional Verification Matrix

This matrix documents the verification results across all components of PyMC Marketing MCP v0.3.0.

| Requirement Area | Test Scenario | Verified Input | Expected Invariant | Actual Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Statistical Baseline** | End-to-end NUTS Sampling | 104 weeks, 4 channels, 1 control | MCMC sampling finishes without error; artifact saved to NetCDF | 4 chains x 200 draws sampled; .nc saved | **PASS** |
| **Contributions** | Channel Posterior Invariants | Fitted Single MMM | Finite intervals, lower <= median <= upper, plausible positive signs | Meta, Google, TikTok, YouTube all within [lower, upper] | **PASS** |
| **Incrementality** | Total vs Marginal iROAS | Fitted Single MMM | Total and marginal iROAS distinct; diminishing returns observed | Marginal iROAS median < Total iROAS median; P(iROAS > 1) in [0, 1] | **PASS** |
| **Scenario Simulation** | Posterior Spend Delta | Meta -20%, Google +15% | Evaluates exact allocation with posterior sampling (not optimization) | Returns paired distribution and P(Scenario > Baseline) | **PASS** |
| **Budget Optimization** | SLSQP Optimization | $200k budget, bounds | Recommended allocation sums to budget and satisfies constraints | Recommended spend: Meta $58k, Google $82k; Sum = $200,000 | **PASS** |
| **Multidimensional MMM** | Riyadh, Jeddah, Dammam Panel | 52 weeks x 3 geos (156 rows) | Rectangular panel validation; 12 channel-geo cells; cell simulation | Cell spend simulated; cell constraints enforced | **PASS** |
| **Lift Test Calibration** | Incrementality Prior Fusion | 2 Lift Tests (Meta, Google) | Calibrated model artifact created with parent linkage | Lineage recorded; parent_model_id populated | **PASS** |
| **Cross-Validation** | TimeSliceCrossValidator | n_init=40, horizon=10, step=10 | Out-of-sample RMSE and NRMSE calculated across rolling folds | Folds evaluated; mean RMSE computed | **PASS** |
| **Prior Sensitivity** | Adstock & Saturation Shift | Altered priors | Quantifies channel rank shifts between baseline and altered priors | Channel rank stability categorized | **PASS** |
| **Extrapolation Risk** | Spend > 1.5x p95 Spend | Relative change +400% | Warning EXTRAPOLATION_RISK emitted with channel & threshold details | Warning returned in envelope | **PASS** |
| **MCP Protocol (stdio)** | Tool & Resource Discovery | stdio subprocess | 17 tools listed; register/validate tools executed; error handled | All 17 tools discovered and verified | **PASS** |
| **MCP Protocol (HTTP)** | Streamable HTTP Client | http://127.0.0.1:port/mcp | Client session initialization, tool calls, error envelope generation | Initialized and verified with mcp.client | **PASS** |
| **Persistence Lifecycle** | Full Server Restart | Register -> Fit -> Restart -> Reload | Model status, diagnostics, and decision execution intact after restart | Successfully reloaded and simulated from SQLite + NetCDF | **PASS** |
| **Failure Protection** | 12 Negative Edge Cases | Bad datasets, security paths | Appropriate DomainError code raised; no crash or unhandled exception | All 12 negative edge cases passed | **PASS** |
