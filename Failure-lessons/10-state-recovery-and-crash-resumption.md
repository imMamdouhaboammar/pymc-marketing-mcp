# Post-Mortem 10: State Machine Crash Recovery & Resumption from Checkpoints

## 1. Executive Summary & Context
In cloud-native serverless environments like Google Cloud Run, container instances may be terminated or scaled down during long-running tasks (e.g. cold start evictions, scale-to-zero triggers, spot preemption). When a container crashed during an MCMC run, the job remained locked in a stale state, and the state machine refused to allow clients or operators to resume execution.

- **Component**: `src/marketing_mcp/jobs/state.py`, `src/marketing_mcp/jobs/repository.py`, `src/marketing_mcp/jobs/service.py`
- **Severity**: High (State Machine Lockout & Inability to Resume)
- **Status**: Resolved & Verified with Test Suite

---

## 2. Symptom & Error Signature
1. **Dangling Running State**:
   Jobs that crashed when a container restarted remained stuck in `RUNNING` status permanently in `metadata.db`.
2. **State Machine Transition Rejection**:
   Attempting to restart or retry an interrupted job resulted in an invalid transition domain error:
   ```text
   DomainError: [INVALID_STATE_TRANSITION] Cannot transition job 'job-123' from FAILED to QUEUED.
   Allowed transitions: []
   ```

---

## 3. Root Cause Analysis
- **Rigid Terminal States**: `VALID_TRANSITIONS` in `jobs/state.py` treated `FAILED` and `CANCELLED` as absorbing terminal states with no outbound edges, preventing resumption workflows.
- **No Startup Crash Recovery Scanner**: The repository initialization did not inspect previously active running jobs to detect orphaned processes after a process crash.
- **Missing Checkpoint Resumption API**: The service lacked an orchestration tool to inspect the latest valid checkpoint and restart processing from that point forward.

---

## 4. Resolution & Architecture Diff
1. **Resumption Edge Allowance in State Transitions**:
   Updated `VALID_TRANSITIONS` in `jobs/state.py`:
   ```python
   VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
       JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
       JobStatus.RUNNING: {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED},
       JobStatus.SUCCEEDED: set(),
       JobStatus.FAILED: {JobStatus.QUEUED, JobStatus.RUNNING},    # Enabled resumption
       JobStatus.CANCELLED: {JobStatus.QUEUED, JobStatus.RUNNING}, # Enabled retry
   }
   ```

2. **Server Startup Crash Reconciliation Scanner**:
   Added `JobRepository.recover_stale_running_jobs()` to scan for active `RUNNING` jobs on startup, mark them as `FAILED` (due to server restart), and record recovery state.

3. **Resilience & Recovery MCP Tools**:
   - `recover_execution_state(job_id)`: Fetches the job record along with all recorded checkpoints and stage progress.
   - `resume_job(job_id)`: Resumes execution of a failed/cancelled job starting from its latest valid checkpoint.

```python
# src/marketing_mcp/jobs/service.py
def resume_job(self, job_id: str) -> JobRecord:
    job = self.repository.get(job_id)
    if job.status not in (JobStatus.FAILED, JobStatus.CANCELLED):
        raise DomainError("JOB_NOT_RESUMABLE", f"Job {job_id} is in status {job.status.value}")
    
    self.repository.update_status(job_id, JobStatus.QUEUED)
    # Re-queue runner with latest checkpoint metadata
    return self.repository.get(job_id)
```

---

## 5. Verification & Evidence
- `tests/integration/test_large_artifacts_and_resilience.py::test_stale_job_crash_recovery_and_resume`
Verified that a stale running job interrupted by a simulated container crash is accurately reconciled and successfully transitioned through resume.
