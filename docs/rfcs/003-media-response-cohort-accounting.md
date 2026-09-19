# RFC 003: Media Response Cohort Accounting vs Customer Acquisition Cohorts

- **Status**: Accepted / Implemented
- **Date**: 2026-09-19
- **Target seam**: `src/marketing_mcp/domain/cohorts/`

## Motivation & Scientific Problem Statement

Marketing analytics frequently conflates two fundamentally different cohort structures:

1. **Customer Acquisition Revenue Cohorts** (CLV / CRM Domain):
   - Cohort anchor: Calendar period when a unique customer transacted for the first time ($t_{\text{acq}}$).
   - Progression: Retention rate, probability alive ($P(\text{alive})$), repeat orders, and monetary realization over time.
   - Microdata: Customer transactions or contractual renewals.
   - Primary Invariant: Never fake or impute individual customer-level microdata when only aggregate data exists.

2. **Media Source-Period Response Cohorts** (MMM / Adstock Domain):
   - Cohort anchor: Calendar period and channel when marketing spend was deployed ($S_{c,t}$).
   - Progression: Immediate response ($t+0$) followed by adstock carryover decay ($t+1, t+2, \dots, t+L$).
   - Physics: Derived from fitted adstock lag transformations (e.g. Geometric, Weibull, Delayed).
   - Primary Invariant: Never build a second uncalibrated adstock engine; reuse the fitted model's posterior adstock weights, and enforce strict reconciliation between the sum of source-period cohort carryovers and the authoritative aggregate calendar response.

Previously, `src/marketing_mcp/domain/cohorts/contracts.py` defined `ResponseCohortLedger` and `CohortRecord` which tracked customer transaction metrics (`acquired_customers`, `period_revenues`), but claimed in documentation to reconcile with "aggregate MMM target series". This created semantic ambiguity.

## Mathematical Specification

### 1. Media Response Cohort Decomposition

For a media channel $c$ with spend $S_{c,t}$ in source period $t$, producing total estimated incremental outcome $R_{c,t}$ across its lifetime horizon, and normalized adstock lag weights $\mathbf{w} = [w_0, w_1, \dots, w_L]$ where $\sum_{l=0}^L w_l = 1$:

$$\text{Response}_{c,t}(\text{lag}=l) = R_{c,t} \cdot w_l \quad \text{for } l \in \{0, 1, \dots, L\}$$

- **Immediate Response**: $\text{Response}_{c,t}(0) = R_{c,t} \cdot w_0$
- **Carryover Response at lag $l$**: $\text{Response}_{c,t}(l) = R_{c,t} \cdot w_l \quad (l \ge 1)$
- **Total Lifetime Response**: $\sum_{l=0}^L \text{Response}_{c,t}(l) = R_{c,t}$

### 2. Reconciliation to Aggregate Calendar Response

At any calendar evaluation period $T$, the total observed or modeled media response from channel $c$ is the sum of contributions from all past source periods $t \le T$ that have non-zero carryover at lag $l = T - t$:

$$\text{CalendarResponse}_c(T) = \sum_{l=0}^{\min(L, T)} \text{Response}_{c, T-l}(l)$$

The ledger must verify reconciliation against the authoritative model target/response series:

$$\left| \sum_{c} \text{CalendarResponse}_c(T) - \text{TargetResponse}(T) \right| \le \epsilon \cdot \text{TargetResponse}(T)$$

where $\epsilon$ is the numerical tolerance (default 5%).

### 3. Financial Valuation

For each media response cohort, financial valuation converts physical response units into monetary valuation using `FinancialAssumptions`:
- **Gross Revenue**: $\text{Revenue}_{c,t} = R_{c,t} \cdot r$ (where $r = \text{revenue\_per\_outcome}$)
- **Net Profit**: $\Pi_{c,t} = \text{Revenue}_{c,t} \cdot m - S_{c,t}$ (where $m = \text{effective\_margin\_rate}$)
- **Cohort ROAS**: $\text{ROAS}_{c,t} = \frac{\text{Revenue}_{c,t}}{S_{c,t}}$ (for $S_{c,t} > 0$)
- **Discounted Net Present Value (NPV)**:
  $$\text{NPV}_{c,t} = \sum_{l=0}^L \frac{\text{Response}_{c,t}(l) \cdot r \cdot m}{(1 + d)^l} - S_{c,t}$$
  where $d$ is the periodic discount rate.

## Architectural Invariants

1. **Explicit Typing**: Customer acquisition records are typed as `CustomerCohortRecord` / `CustomerAcquisitionCohortLedger`. Media response cohorts are typed as `MediaResponseCohortRecord` / `MediaResponseCohortLedger`.
2. **Backward Compatibility**: `CohortRecord` and `ResponseCohortLedger` are preserved as aliases for customer cohorts to avoid breaking existing callers.
3. **No Fabricated Adstock**: Adstock weights come directly from fitted PyMC-Marketing adstock configurations; no heuristic adstock formulas are introduced.
4. **Reconciliation Guarantee**: Media cohorts provide `reconcile_to_calendar_response` verifying mathematical conservation of response mass over time.
