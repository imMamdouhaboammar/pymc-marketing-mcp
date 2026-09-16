# Post-Mortem 09: MCP Call Collapse, HTTP Timeouts & Intermediate State Checkpointing

## 1. Executive Summary & Context
Bayesian inference algorithms (NUTS, MCMC) on complex Marketing Mix Models and hierarchical CLV models inherently require prolonged computation times (2 to 15 minutes). Standard AI client connections (Claude Desktop, Cursor, ChatGPT) enforce aggressive client-side HTTP timeouts (typically 60 to 120 seconds). Under a monolithic execution model, long model fits resulted in connection dropouts, lost results, and wasteful restart cycles.

- **Component**: `src/marketing_mcp/jobs/service.py`, `src/marketing_mcp/jobs/repository.py`, `src/marketing_mcp/storage/migrations.py`
- **Severity**: High (Operation Interruption & Lost Compute)
- **Status**: Resolved & Verified with Test Suite

---

## 2. Symptom & Error Signature
AI client interaction windows reported:
```text
Tool 'fit_mmm' failed: HTTP Request Timed Out (after 120s).
```
On the server side:
- The worker continued MCMC sampling in background isolation.
- However, the client's RPC session had collapsed, leaving the completed posterior orphaned without an active listener to capture the artifact digest.
- AI clients were forced to restart the entire fit pipeline from step 0.

---

## 3. Root Cause Analysis
- **Monolithic Invocations**: MCP tools executed heavy mathematical jobs synchronously inside a single blocking call.
- **Absence of Intermediate Checkpoints**: The database only tracked coarse lifecycle states (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`). It lacked granular checkpoints to record sub-stage milestones.
- **No Heartbeat Polling Mechanism**: No lightweight polling contract existed for AI clients to check execution status without triggering request timeouts.

---

## 4. Resolution & Architecture Diff
1. **Migration 4: `job_checkpoints` Persistence**:
   Created a dedicated SQLite schema to persist sub-stage progress persistently:
   ```sql
   CREATE TABLE job_checkpoints (
       checkpoint_id TEXT PRIMARY KEY,
       job_id TEXT NOT NULL,
       stage TEXT NOT NULL,
       status TEXT NOT NULL,
       progress_pct REAL DEFAULT 0.0,
       metadata JSON,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY(job_id) REFERENCES jobs(job_id)
   );
   ```

2. **Standardized Stage Checkpoints**:
   Enforced explicit checkpoints across the lifecycle:
   - `DATA_PREPARATION` (0-10%)
   - `PRIOR_SPECIFICATION` (10-20%)
   - `MCMC_SAMPLING` (20-75%)
   - `POSTERIOR_PROCESSING` (75-85%)
   - `DIAGNOSTICS_COMPUTED` (85-95%)
   - `ARTIFACT_SERIALIZATION` (95-100%)

3. **Bounded Heartbeat Polling Tool (`poll_job_progress`)**:
   Exposed an asynchronous polling tool with a short, bounded wait window (`timeout_seconds=5`), allowing AI clients to poll progress safely:
   ```python
   # src/marketing_mcp/mcp/tools/jobs.py
   @app.tool()
   def poll_job_progress(job_id: str, timeout_seconds: int = 5) -> dict:
       return job_service.poll_job(job_id, timeout_seconds=timeout_seconds)
   ```

---

## 5. Verification & Evidence
- `tests/integration/test_large_artifacts_and_resilience.py::test_checkpoint_registration_and_progress_polling`
Verified that progress updates through multiple stages and intermediate state checkpoints are cleanly queryable without timeout.
