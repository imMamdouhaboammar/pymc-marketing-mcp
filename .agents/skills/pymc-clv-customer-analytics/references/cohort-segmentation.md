# Customer Cohort Segmentation & Retention Playbook

Translate Bayesian CLV and $P(\text{alive})$ metrics into automated CRM and retention marketing actions.

---

## 1. The 2D Customer Value Matrix

```text
               High Expected CLV
                     │
       [At-Risk VIPs]│ [Champions]
       (Low P_alive, │ (High P_alive,
        High Spend)  │  High Spend)
  ─── P(alive) = 0.50 ┼─────────────────── High P(alive)
       [Lost Souls]  │ [Promising]
       (Low P_alive, │ (High P_alive,
        Low Spend)   │  Low Spend)
                     │
               Low Expected CLV
```

---

## 2. Segment Action Protocols

1. **Champions ($P(\text{alive}) > 0.80$, High CLV)**:
   - Strategy: Protect and reward.
   - Tactics: Exclusive loyalty tiers, early access to new collections, referral incentives.
2. **At-Risk VIPs ($P(\text{alive}) \in [0.20, 0.50]$, High Historical Spend)**:
   - Strategy: Urgent retention intervention.
   - Tactics: Direct concierge email, win-back discount voucher, CS satisfaction check.
3. **Lost Customers ($P(\text{alive}) < 0.10$)**:
   - Strategy: Spend reduction.
   - Tactics: Suppress from paid retargeting lists (Google Customer Match, Meta Custom Audiences) to stop ad waste.
