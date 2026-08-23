# Incrementality Triangulation Framework

Triangulation integrates multiple measurement methodologies to overcome the individual weaknesses of each approach.

---

## 1. The Measurement Hierarchy

```
Level 1: Causal Truth Anchor ──> Geo-Lift Tests & Randomized Control Trials (RCTs)
                                      │ (Calibrates)
Level 2: Macro Strategic Engine ──> Bayesian Marketing Mix Modeling (MMM)
                                      │ (Informs baseline & decay)
Level 3: Tactical Execution ────> Multi-Touch Attribution / Platform Analytics (MTA)
```

---

## 2. Resolving Discrepancies

### Case A: MTA Claims High ROI, MMM / Lift Test Shows Low ROI
- **Typical Channels**: Brand Search, Retargeting, Affiliate Coupon Sites.
- **Root Cause**: Selection Bias. Customers already intended to purchase and clicked the paid link as an organic navigation shortcut.
- **Resolution**: Anchor the channel parameter in the MMM using a holdout experiment where the channel was turned off in 50% of markets. Reallocate budget toward truly incremental acquisition channels.

### Case B: MMM Claims High ROI, MTA Claims Near Zero
- **Typical Channels**: TV, Out of Home (OOH), Brand Sponsorships, Podcast Ads.
- **Root Cause**: Attribution Blindness. Non-clickable, upper-funnel impressions generate offline awareness that manifests as organic search or direct traffic weeks later.
- **Resolution**: Trust the MMM posterior delayed adstock estimates. Validate with a pulsed flighting test.
