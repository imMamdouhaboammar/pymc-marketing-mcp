# Media Flighting Strategies & Campaign Scheduling

Media flighting schedules media spend across time (weeks/months) rather than assuming a static constant spend rate.

---

## 1. Flighting Patterns Explained

```
Flat (Continuous):
Spend │ ── ── ── ── ── ── ── ──
      └─────────────────────────> Time

Frontloaded (Launch / Push):
Spend │ ██ ▇▇ ▅▅ ▄▄ ▃▃ ▂▂ ── ──
      └─────────────────────────> Time

Backloaded (Deadline / Holiday):
Spend │ ── ── ▂▂ ▃▃ ▄▄ ▅▅ ▇▇ ██
      └─────────────────────────> Time

Pulsed (Flighting + Hiatus):
Spend │ ██ ── ██ ── ██ ── ██ ──
      └─────────────────────────> Time
```

---

## 2. Exploiting Adstock Decay via Pulsing

When a media channel has high adstock retention ($\alpha \ge 0.6$ or delayed peak):
1. **Burst Period**: High spend builds a large pool of effective advertising capital ($\text{Adstock}_t$).
2. **Hiatus Period (Dark Week)**: Zero or minimal spend occurs, but because $\text{Adstock}_{t+1} = \alpha \cdot \text{Adstock}_t$, customer sales response decays slowly.
3. **Efficiency Gain**: Pulsing prevents the channel from staying in the severe flat portion of its saturation curve continuously, delivering higher total response per dollar.

---

## 3. Flighting Strategy Matrix

| Business Goal | Optimal Pattern | Primary Objective | Key Channels |
|---|---|---|---|
| **E-Commerce Black Friday / Q4** | `backloaded` | `maximize_net_profit` | Meta, Google Shopping, Affiliate |
| **New Brand or Product Launch** | `frontloaded` | `maximize_response` | Connected TV, YouTube, PR, Influencers |
| **B2B SaaS Annual Pipeline** | `flat` with quarterly `pulsed` bursts | `target_roas` | LinkedIn, Google Search, Webinars |
| **High-Adstock CPG / Auto** | `pulsed` | `maximize_net_profit` | Linear TV, Digital Video, OOH |
