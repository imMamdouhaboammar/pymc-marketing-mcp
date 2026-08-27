# Dynamic Media Flighting Strategies

Media flighting schedules spend across multi-week planning horizons accounting for adstock memory decay.

---

## 1. Flighting Patterns

### A. Flat / Continuous Allocation
- Uniform spend $x_{k, t} = B_k / T$ across all weeks $t \in \{1, \dots, T\}$.
- Optimal for channels with zero or low carryover ($lpha \approx 0$) such as Brand Search or direct performance retargeting.

### B. Pulsed Flighting
- Alternates high-spend burst weeks with zero or maintenance-spend dark weeks.
- Exploits high adstock carryover ($lpha > 0.6$):
  $$\text{Adstock}_t = x_t + \alpha \cdot \text{Adstock}_{t-1}$$
- While spend $x_t = 0$ in week $t$, effective adstock remains high, delivering continuous brand impact at lower total cost.

### C. Frontloaded Flighting
- Concentrates $50\%$ of budget in the first $25\%$ of campaign weeks.
- Best for product launches, brand pivots, or major promotional events.

### D. Backloaded Flighting
- Escalates spend toward end of period (e.g. Q4 holiday peak).
