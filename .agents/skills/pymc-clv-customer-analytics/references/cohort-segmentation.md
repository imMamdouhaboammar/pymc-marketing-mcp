# Customer Cohort Segmentation & Retention Playbook

Translate Bayesian CLV and $P(\text{alive})$ metrics into CRM and retention marketing actions.

---

> [!IMPORTANT]
> The server tool `get_churn_risk_cohorts` is the authoritative primitive for programmatic cohort evaluation, utilizing a configurable churn risk threshold (default `0.30`). The segmentation bands below provide an illustrative CRM operational playbook for multi-tier lifecycle marketing campaigns and should be adapted to the business domain.

---

## 1. Customer Value Matrix (Illustrative Operational Tiers)

A complete partition across the full $P(\text{alive}) \in [0.0, 1.0]$ spectrum:

- **Champions ($P(\text{alive}) \ge 0.80$, High Expected CLV)**:
  - High engagement and recent transaction activity.
  - Action: Protect and reward with premium loyalty benefits, VIP early access, and advocacy invitations.
- **Stable Loyalists ($P(\text{alive}) \in [0.50, 0.80)$)**:
  - Consistent repeat behavior with moderate decay risk.
  - Action: Nurture with routine product recommendations, cross-sell campaigns, and seasonal incentive programs.
- **At-Risk VIPs ($P(\text{alive}) \in [0.20, 0.50)$, High Historical Spend)**:
  - Substantial historical value but declining recency/frequency; high priority for retention intervention.
  - Action: Immediate retention outreach, personalized discount offers, or relationship manager touchpoints.
- **Cooling Down ($P(\text{alive}) \in [0.10, 0.20)$)**:
  - Infrequent purchase cadence nearing lapse state.
  - Action: Low-cost re-engagement drip sequences; evaluate price sensitivity before aggressive discounting.
- **Lost / Dormant ($P(\text{alive}) < 0.10$)**:
  - Very low probability of active state.
  - Action: Suppress from expensive paid retargeting lists to eliminate ad waste; route to ultra-low-cost reactivation or purge from CRM active sync.
