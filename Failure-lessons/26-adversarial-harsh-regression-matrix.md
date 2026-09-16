# Failure Lesson 26: Adversarial Harsh Regression Matrix & Golden Test Fixtures

## 1. Executive Summary & Context
- **Component**: `migration/baselines/golden_datasets/`, `tests/fixtures/`, `tests/integration/test_adversarial_harsh_regression_matrix.py`
- **Severity**: P1 Data Quality & Reliability Architecture
- **Symptom**: Lack of standardized adversarial test fixtures resulted in regressions around time series gaps (e.g., 234 observed days out of 243 calendar days), collinear marketing channels, invalid or corrupt inputs, and CLV purchase invariants going undetected until manual adversarial testing.

## 2. Root Cause Analysis
- Unit and integration tests relied on ad-hoc synthetic datasets generated on the fly inside test bodies.
- There was no permanent fixture library testing the exact edge cases discovered during harsh adversarial audits:
  - Daily time series tracking outages (intermittent missing calendar days)
  - Severe multicollinearity between ad channels (e.g. Meta Ads vs Facebook Ads, r > 0.99)
  - Corrupt or malformed input rows (duplicate timestamps, missing values, string media values)
  - CLV customer transactional RFM boundary constraints (`T >= recency >= 0`, `monetary_value > 0`)

## 3. Resolution & Fix
- Created 6 standardized golden harsh fixtures in both `migration/baselines/golden_datasets/` and `tests/fixtures/`:
  1. `pymc_harsh_observed_daily_panel.csv`: 234 observed daily periods across 243 calendar days with 9 calendar gaps and spend/revenue outliers.
  2. `pymc_harsh_continuous_zero_padded_panel.csv`: 243 continuous days with zero-padded gaps for clean baseline comparisons.
  3. `pymc_harsh_invalid_panel.csv`: Panel with duplicate dates, missing values, and invalid non-numeric strings.
  4. `pymc_harsh_collinear_panel.csv`: 52 weekly periods with collinear channels (`meta` and `facebook_ads`, r > 0.99).
  5. `pymc_harsh_clv_valid_fixture.csv`: 100 customer records satisfying BG/NBD purchase frequency, recency, and tenure constraints.
  6. `pymc_harsh_clv_value_fixture.csv`: Customer spend records with repeat purchases and positive monetary values for Gamma-Gamma models.
- Implemented `tests/integration/test_adversarial_harsh_regression_matrix.py` asserting exact detection and validation behavior across all 6 fixtures.
- Hardened matplotlib plotting in `src/marketing_mcp/services/plotting_service.py` to wrap `fig.savefig` in `try ... finally: plt.close(fig)` to prevent memory leaks during batch plot rendering.

## 4. Verification & Prevention
- Verified all 7 harsh regression tests pass in 3.69s:
  - `test_harsh_fixture_observed_daily_panel_detects_temporal_gaps` PASSED
  - `test_harsh_fixture_continuous_zero_padded_panel_passes_validation` PASSED
  - `test_harsh_fixture_invalid_panel_detects_all_structural_violations` PASSED
  - `test_harsh_fixture_collinear_panel_detects_high_channel_correlation` PASSED
  - `test_harsh_fixture_clv_valid_rfm_contract` PASSED
  - `test_harsh_fixture_clv_value_repeat_spend_contract` PASSED
  - `test_app_e2e_register_and_validate_harsh_datasets` PASSED
