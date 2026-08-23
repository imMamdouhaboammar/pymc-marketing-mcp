# Customer Cohort Segmentation & Equity Strategy

Segmenting customers by $P(\text{alive})$ and expected monetary value enables prioritized retention marketing.

---

## 1. The 2x2 Retention Grid

```
High Value │ Champions (P(alive) > 0.8)     │ At-Risk Whales (P(alive) 0.2-0.5)
           │ -> VIP loyalty, upsell         │ -> High-touch winback, discounts
───────────┼────────────────────────────────┼───────────────────────────────────
Low Value  │ Low-Touch Active (P(alive)>0.8)│ Hibernating / Lost (P(alive)<0.1)
           │ -> Automated newsletters       │ -> Suppress ad spend, purge email
           └────────────────────────────────┴───────────────────────────────────
                        Active                          At-Risk / Churned
```

---

## 2. Retention Playbook Rules

1. **At-Risk Whales**:
   - Condition: $P(\text{alive}) \le 0.30$ AND Historical Spend $> \text{80th percentile}$.
   - Action: Direct phone outreach from account executive or high-value gift/credit.
2. **Paid Ad Audience Suppression**:
   - Condition: $P(\text{alive}) \le 0.10$ AND Inactive $> 180$ days.
   - Action: Exclude from Meta/Google retargeting custom audiences to save ad budget.
3. **Early Churn Intervention**:
   - Monitor expected purchases drop rate week-over-week.
