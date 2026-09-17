# Marketing Data Intelligence Engine

The **Marketing Data Intelligence Engine** sits logically *before* PyMC and PyMC-Marketing. It ensures the platform reliably understands unfamiliar real-world marketing data before attempting Bayesian statistical modeling or budget optimization.

```text
Raw Dataset (CSV / Parquet)
           ↓
Marketing Data Intelligence Engine
  ├── 1. Structural Profiling (Shape, Memory, Nulls, Gaps, Quantiles)
  ├── 2. Semantic Role Inference (Target, Channels, Currencies, Controls, Dims)
  ├── 3. Marketing Domain Intelligence (Lifecycles, Mixed Objectives, Outages)
  ├── 4. Statistical Suitability Diagnostics (Variance, Collinearity, Sparsity)
  ├── 5. Analysis Suitability (MMM, Panel MMM, CLV)
  └── 6. Explainable Transformation Planning (Pivoting, Aggregation, Alignment)
           ↓
Semantic Dataset Contract (Typed, Evidence-Backed, Inspectable)
           ↓
PyMC / PyMC-Marketing Bayesian Statistical Modeling
           ↓
Decision Safety & Decision Gate
```

---

## 1. What the Engine Does

- **Understands unfamiliar marketing data**: Inspects column types, distributions, temporal continuity, and marketing semantics without assuming fixed column names.
- **Evidence-First Inference**: Produces typed, structured evidence signals for every classification (e.g. why `google_spend` is a channel, why `meta_reported_revenue` is an attributed target).
- **Guards Downstream Modeling**: Prevents fitting invalid models silently (e.g. running MMM on non-rectangular panels, sparse media, or mixed funnel objectives).
- **Proposes Transformations**: Identifies when data requires pivoting or aggregation without silently mutating the analyst's data.
- **Enforces User Overrides**: Allows explicit human or agent configuration to outrank heuristic inference with 1.0 confidence.

## 2. What the Engine Does Not Do

- **Does not replace PyMC / PyMC-Marketing**: All Bayesian parameter estimation, MCMC sampling, adstock carryover, saturation curves, and posterior inference remain in PyMC-Marketing.
- **Does not silently mutate user data**: It produces an explainable `TransformationPlan`; mutations are explicit downstream choices.
- **Does not confuse heuristic confidence with probability**: Scores indicate heuristic rule alignment, not Bayesian posterior probabilities.
- **Does not approve decision safety autonomously**: Media budget allocation safety also depends on MCMC convergence, out-of-sample cross-validation, and posterior predictive checks.

---

## 3. Deterministic vs Heuristic Inference

The engine adheres to the principle: **Deterministic when possible, statistical when necessary, Bayesian when uncertainty matters.**

- **Deterministic Profiling**:
  - Null counts, percentages, and longest contiguous missing runs.
  - Non-negative constraints (`spend >= 0`).
  - Date gap discovery against continuous calendars.
  - Zero spend counts and duplicate period keys.
- **Heuristic Semantic Inference**:
  - Identifying media platforms vs generic numeric columns.
  - Distinguishing independent total business revenue from platform-attributed revenue.
  - Recommending modeling strategies (pooled global vs separate vs hierarchical panel).
- **Statistical Diagnostics**:
  - Spend variation (CV = std / mean).
  - Pairwise channel collinearity (r >= 0.90) and matrix condition numbers.
  - Multi-factor identifiability risk synthesis.

---

## 4. Confidence Semantics

Every inferred column receives a `HeuristicConfidence`:

```python
class ConfidenceLevel(str, Enum):
    HIGH = "high"       # score >= 0.75: strong naming + valid distributions
    MEDIUM = "medium"   # score >= 0.50: partial match or ambiguous naming
    LOW = "low"          # score < 0.50: fallback or weak heuristic
```

The numerical `score` is an explicit heuristic compatibility index. It is **never** represented as a Bayesian posterior probability.

---

## 5. Manual Overrides

Analyst overrides strictly outrank heuristic inference:

```python
overrides = {
    "custom_spend_col": {"role": SemanticRole.MEDIA_CHANNEL, "semantic_type": "spend"},
    "gross_revenue": {"role": SemanticRole.TARGET, "semantic_type": "revenue"},
}
contract = engine.analyze_dataset(df, user_overrides=overrides)
assert contract.columns["custom_spend_col"].user_overridden is True
assert contract.columns["custom_spend_col"].confidence.score == 1.0
```

---

## 6. Standardized Marketing Issues Catalogue

| Issue Code | Default Severity | Description | Downstream Consequence |
| :--- | :--- | :--- | :--- |
| `MIXED_CONVERSION_SEMANTICS` | `WARNING` | Funnel mixes awareness/traffic and conversion campaigns | Distorts adstock decay and ROI curves |
| `AMBIGUOUS_TARGET` | `WARNING` | Multiple plausible revenue/orders target columns | Surfaces clarification request to user |
| `ATTRIBUTED_REVENUE_TARGET` | `WARNING` | Target represents pixel/platform-attributed revenue | Causal attribution confounding |
| `CURRENCY_INCONSISTENCY` | `HIGH` | Discrepancy between local and normalized monetary fields | Distorts spend scale and ROI priors |
| `STAGGERED_CHANNEL_LIFECYCLE`| `WARNING` | Channels active in disjoint time periods (< 25% overlap) | Temporal confounding with macro trend |
| `INSUFFICIENT_HISTORY` | `BLOCKING` / `WARNING` | Fewer than 26 periods (blocking) or < 52 periods | Poor NUTS posterior parameter recovery |
| `SPARSE_CHANNEL` | `WARNING` | Channel active in < 25% of timeline | Posterior shrinkage distortion |
| `LOW_VARIATION_CHANNEL` | `WARNING` | Near-constant spend (CV < 0.05) | Non-identifiable saturation curve |
| `HIGH_CHANNEL_COLLINEARITY` | `WARNING` | Pairwise correlation r >= 0.90 | Multicollinearity & wide credible intervals |
| `MARKET_HETEROGENEITY` | `WARNING` | Geo column present but dims=[] provided | Pools diverse market dynamics |
| `POSSIBLE_TARGET_TRACKING_GAP` | `WARNING` | Active media spend observed when target == 0 | Telemetry dropout or attribution lag |
| `NON_RECTANGULAR_PANEL` | `BLOCKING` | Missing date × dimension combinations | PyMC tensor dimension mismatch |

---

## 7. Example Workflows

### Example A: Clean Dataset
```python
df = pd.DataFrame({
    "date": pd.date_range("2025-01-06", periods=65, freq="W-MON"),
    "revenue": [50000.0 + i * 200 for i in range(65)],
    "google_spend": [2000.0 + (i % 3) * 200 for i in range(65)],
    "meta_spend": [1500.0 + (i % 4) * 150 for i in range(65)],
})
contract = engine.analyze_dataset(df)
# Result: Suitability = SUITABLE, modeling_contract generated ready for fit_mmm()
```

### Example B: Dirty / Sparse Dataset
```python
df = pd.DataFrame({
    "date": pd.date_range("2025-01-06", periods=20, freq="W-MON"), # only 20 periods
    "revenue": [5000.0] * 20,
    "constant_spend": [100.0] * 20,                                  # zero variation
    "sparse_channel": [0.0] * 18 + [50.0, 50.0],                     # 2 active periods
})
contract = engine.analyze_dataset(df)
# Result: Suitability = NOT_SUITABLE
# Blockers: ["Fewer than 26 time periods available (20 periods)"]
# Warnings: ["LOW_VARIATION_CHANNEL", "SPARSE_CHANNEL"]
```

### Example C: Multi-Market Dataset
```python
df = pd.DataFrame({
    "date": pd.date_range("2025-01-06", periods=40, freq="W-MON").tolist() * 3,
    "market": ["US"] * 40 + ["UK"] * 40 + ["DE"] * 40,
    "revenue": [10000.0] * 120,
    "spend": [100.0] * 120,
})
contract = engine.analyze_dataset(df, dims=["market"])
# Result: Recommends hierarchical_panel strategy across 3 confirmed markets
```

### Example D: Mixed-Objective Dataset
```python
df = pd.DataFrame({
    "date": pd.date_range("2025-01-06", periods=30, freq="W-MON").tolist() * 2,
    "objective": ["Sales"] * 30 + ["Awareness"] * 30,
    "revenue": [10000.0] * 30 + [0.0] * 30,
    "spend": [100.0] * 60,
})
contract = engine.analyze_dataset(df)
# Result: Issues = [MIXED_CONVERSION_SEMANTICS]
# Understands that Awareness campaigns legitimately have zero direct revenue.
```

### Example E: Ambiguous Target Dataset
```python
df = pd.DataFrame({
    "date": pd.date_range("2025-01-06", periods=60, freq="W-MON"),
    "ecommerce_revenue": [10000.0 + i * 100 for i in range(60)],
    "crm_gross_revenue": [12000.0 + i * 110 for i in range(60)],
    "google_spend": [1000.0] * 60,
})
contract = engine.analyze_dataset(df)
# Result: Issues = [AMBIGUOUS_TARGET]
# ClarificationRequest: surfaces exact choice between ecommerce_revenue and crm_gross_revenue
```

---

## 8. Measured Benchmarks

Benchmark execution on Apple M-series (Python 3.12, single core):

| Dataset Size | Memory Footprint | Profiling & Semantic Time | Throughput |
| :--- | :--- | :--- | :--- |
| **10,000 rows** | 1.1 MB | 0.045 seconds | 221,007 rows/sec |
| **100,000 rows** | 10.5 MB | 0.202 seconds | 495,710 rows/sec |
| **500,000 rows** | 52.7 MB | 0.873 seconds | 572,557 rows/sec |

The engine executes sub-second analysis across half a million records without requiring distributed frameworks or native C/Rust extensions.
