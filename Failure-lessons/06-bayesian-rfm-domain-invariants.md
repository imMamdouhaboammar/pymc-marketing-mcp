# Post-Mortem 06: Bayesian RFM Mathematical Domain Invariants

## 1. Executive Summary & Context
During testing of the Bayesian Customer Lifetime Value (CLV) BG/NBD model on the remote Cloud Run environment, the model fitting step failed with a validation error from `pymc_marketing.clv`:
`ValueError: recency cannot be greater than 0 if frequency is 0`.

- **Component**: Mathematical Data Validation & Preflight Checks
- **Severity**: High (Statistical Model Convergence Failure)
- **Time to Detect**: During MCMC sampling invocation on synthetic dataset
- **Status**: Codified as a Strict Invariant & Documented

---

## 2. Symptom & Error Signature
Tool call `fit_clv_model` returned:
```text
ValueError: recency cannot be greater than 0 if frequency is 0
  at pymc_marketing/clv/models/rfm.py:112 in _validate_data
```

---

## 3. Root Cause Analysis
This error reflects a fundamental mathematical domain invariant of Bayesian Buy-Till-You-Die (BTYD) count models (specifically the Pareto/NBD and BG/NBD frameworks established by Fader, Hardie, and Lee):

1. **RFM Notation Definitions**:
   - $x$ (`frequency`): Number of **repeat** transactions observed in the customer history $(0, T]$. (The initial transaction at time 0 is the conditioning event and does not count as a repeat transaction).
   - $t_x$ (`recency`): Time elapsed between the initial transaction and the **most recent** transaction.
   - $T$: Total observation window length from the initial transaction to the end of the study period.
2. **Mathematical Invariant**:
   - If a customer made **zero** repeat purchases ($x = 0$), their only transaction occurred at $t = 0$. Therefore, their recency $t_x$ is mathematically defined as $0.0$.
   - A customer cannot have a positive recency without having had a transaction at that time.
   - Furthermore, $0 \le t_x \le T$ must hold for all customers (a transaction cannot occur in the future beyond observation time $T$).
3. **Synthetic Generator Flaw**:
   A naive test data generator drew `frequency`, `recency`, and `T` independently from uniform or normal distributions without constraining $x = 0 \implies t_x = 0$.

---

## 4. Resolution & Architecture Invariants
1. **Mathematical Correction**:
   Whenever preparing or generating RFM datasets for PyMC-Marketing:
   ```python
   # Enforce Bayesian RFM domain invariants
   df.loc[df["frequency"] == 0, "recency"] = 0.0
   df["recency"] = df[["recency", "T"]].min(axis=1)
   ```
2. **Preflight Invariant Validation**:
   Preflight data verification tools now check this invariant during dataset registration and validation before allocating compute or initiating MCMC sampling chains.
3. **Golden Fixtures**:
   Pre-validated golden datasets (`valid_clv.csv` and `synthetic_mmm.csv`) were seeded directly into the persistent storage inbox.

---

## 5. Verification & Evidence
- Fitting the BG/NBD model on `valid_clv.csv` with 2 chains, 50 tuning steps, and 50 posterior draws completed in 18.2 seconds on Cloud Run.
- Diagnostic gates evaluated MCMC health with 0 divergences and $\hat{R} \le 1.05$.
- Model successfully produced posterior expected purchases and survival curves.
