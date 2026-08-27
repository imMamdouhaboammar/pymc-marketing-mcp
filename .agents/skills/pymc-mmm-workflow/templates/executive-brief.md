# Executive Marketing Mix Modeling Summary: [Brand Name]

## 1. Executive Summary & Diagnostic Readiness
- **Model ID**: `mmm_ecommerce_q3_2026` (Dataset SHA: `e4b3c9a1...`)
- **Diagnostic Decision Status**: `approved` (Divergences: 0, Max $\hat{R}$: 1.006, Min Bulk ESS: 920, Posterior Coverage: 91.2%)
- **Analyzed Horizon**: 2024-01-01 to 2026-06-30 (130 weekly observations)
- **Top Finding**: Search Non-Brand and Meta are the primary growth engines with marginal iROAS $> 1.8$, while Linear TV has reached severe saturation with marginal iROAS of $0.38.

## 2. Channel Performance & Incrementality Table
| Channel | Total Spend ($) | Attributed Revenue (Median [94% HDI]) | Revenue Share | Total iROAS | Marginal iROAS | P(iROAS > 1.0) |
|---|---|---|---|---|---|---|
| **Search Non-Brand** | $450,000 | $1,575,000 [$1,380,000 - $1,790,000] | 31.5% | 3.50 | 2.15 | 99.9% |
| **Meta Direct Response** | $600,000 | $1,680,000 [$1,490,000 - $1,880,000] | 33.6% | 2.80 | 1.82 | 99.4% |
| **Search Brand** | $250,000 | $1,125,000 [$1,010,000 - $1,240,000] | 22.5% | 4.50 | 1.10 | 97.2% |
| **YouTube Video** | $300,000 | $420,000 [$290,000 - $560,000] | 8.4% | 1.40 | 0.95 | 78.4% |
| **Linear TV** | $500,000 | $200,000 [$110,000 - $310,000] | 4.0% | 0.40 | 0.38 | 2.1% |
| **Base / Organic / Macro** | N/A | $4,500,000 [$4,200,000 - $4,820,000] | -- | -- | -- | -- |

## 3. Saturation & Efficiency Analysis
- **High-Yield Marginal Channels**: Search Non-Brand (Marginal iROAS = 2.15) and Meta (Marginal iROAS = 1.82) are operating on the steep segment of their response curves. Each additional dollar allocated here produces positive net return.
- **Saturated Channels**: Linear TV is deeply saturated (Marginal iROAS = 0.38), losing 62 cents on the marginal dollar spent at current $500k spend levels.
- **Brand Search Baseline**: High historical total iROAS (4.50) reflects capture of existing intent, but low marginal iROAS (1.10) indicates limited upside from increased spending.

## 4. Strategic Budget Recommendations
1. **Reallocate $150,000 from Linear TV to Search Non-Brand and Meta** to capture high-marginal-return demand.
2. **Cap Search Brand budget at current run-rate** to prevent bidding inflation on captured demand.
3. **Execute a matched-market geo-test on Linear TV** before Q4 to calibrate long-term brand equity priors (activate `pymc-lift-calibration`).
