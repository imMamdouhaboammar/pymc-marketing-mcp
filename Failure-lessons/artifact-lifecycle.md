# Failure Lessons: Artifact Lifecycle & Atomic Publication

This document captures durable failure lessons, root causes, and architectural invariants for model artifact materialization, storage, and publication lifecycle in `pymc-marketing-mcp`.

---

## ART-001: Frozen Dataclass In-Place Mutation Crash at Job Completion

### What happened
At the conclusion of an MCMC sampling run, the background worker attempted to finalize artifact metadata before registration. The process crashed with:
```text
dataclasses.FrozenInstanceError: cannot assign to field 'size_bytes'
```
This marked the entire job as `FAILED`, discarding minutes of CPU/GPU computation.

### Why it mattered
* **Wasted Computation**: Bayesian MCMC runs are computationally expensive (10–30 minutes of NUTS sampling). Failing at the final metadata write stage is catastrophic to cost and user trust.
* **Orphaned Storage**: The physical NetCDF posterior trace had already been written to disk, but the failure left an unindexed orphan file in local storage without metadata tracking.

### Observable symptom
* Job status abruptly transitioned from `RUNNING (95%)` to `FAILED (100%)`.
* Error log: `FrozenInstanceError: cannot assign to field 'size_bytes' in storage/metadata.py`.

### Initial assumption
Developers assumed that `ArtifactRef` was a standard mutable Python dataclass, allowing field assignment:
```python
artifact.size_bytes = os.path.getsize(target_path)
artifact.hash = compute_sha256(target_path)
```

### Root cause
* **Status**: Confirmed.
* `ArtifactRef` was designed with `@dataclass(frozen=True)` to guarantee hashability, thread-safety, and immutability across concurrent async handlers.
* Attempting in-place attribute assignment on a frozen instance raises `FrozenInstanceError` at runtime in CPython.

### Why the system allowed it
Python does not enforce immutability at compile time. The artifact registration code was tested with lightweight mock objects that did not enforce dataclass freezing.

### Fix
1. Replaced in-place mutations with `dataclasses.replace`:
```python
artifact = dataclasses.replace(
    artifact,
    size_bytes=os.path.getsize(target_path),
    hash=compute_sha256(target_path),
)
```
2. Added comprehensive unit tests asserting immutability behavior and `replace` roundtrips.

### Verification
* `tests/unit/test_hard_test_remediation.py::test_artifact_ref_immutability_and_replace`
* Verified that updating fields via `dataclasses.replace` returns a valid, immutable instance with updated metadata without raising `FrozenInstanceError`.

### Prevention rule
> **Rule**: Immutable domain objects must never be mutated in place. Always derive updated instances via `dataclasses.replace()` or pure constructors.

### Reusable lesson
Whenever a domain object is marked `frozen=True`, audit all downstream consumers for legacy in-place assignments. Configure static linters (mypy / pyright) to flag frozen attribute writes.

---

## ART-002: Non-Atomic Artifact Publication & Premature State Exposure

### What happened
An autonomous client polling `get_job` observed `status: "completed"`. The client immediately dispatched a subsequent request to `get_model` and `optimize_budget`, which failed with:
```text
ModelNotFoundError: Model 'mmm_789' not found in registry
```
A few hundred milliseconds later, querying the same model ID succeeded.

### Why it mattered
* **Race Condition for AI Agents**: AI agents polling job status execute rapidly. Exposing a `completed` state before physical artifacts are committed and registered in memory breaks autonomous execution loops.
* **Partial State Exposure**: If a container restarted during the window between job status update and file flush, the job appeared completed in the database but the artifact file was corrupt or missing.

### Observable symptom
* Intermittent 404/NotFound errors on newly completed models immediately following completion status events.
* Ambiguity between "model does not exist" and "model is still publishing".

### Initial assumption
Developers assumed updating the job record status to `completed` in the database was the final step and that disk I/O was fast enough that synchronization gaps were negligible.

### Root cause
* **Status**: Confirmed / Strongly indicated.
* Non-atomic lifecycle pipeline. The background worker executed steps in an inverted order:
  1. Updated database job status to `COMPLETED`.
  2. Finished streaming/flushing large NetCDF blobs (100MB–1GB) to permanent disk.
  3. Computed checksums and registered model metadata in `ModelRegistry`.
* Any query arriving during steps 2 or 3 received `COMPLETED` from the job API, but `ModelNotFoundError` from the registry.

### Why the system allowed it
The system lacked a strictly enforced, transactional staging-to-commit publication pipeline.

### Fix
1. **Enforced Atomic Publication Pipeline**:
   $$\text{Serialize to Staging} \longrightarrow \text{Validate Integrity \& Checksum} \longrightarrow \text{Atomic Move } (os.replace) \longrightarrow \text{Register in Registry} \longrightarrow \text{Expose SUCCEEDED State}$$
2. **Atomic Inode Replacement**: Artifacts are written to a `.tmp` staging path on the same filesystem and atomically moved via `os.replace` (POSIX `rename`).
3. **Distinct Error Semantics**: Differentiated `NOT_FOUND` (unknown ID) from `NOT_READY` (job still finalizing or artifact staging in progress).

### Verification
* `tests/unit/test_hard_test_remediation.py::test_atomic_artifact_publication_sequence`
* `tests/integration/test_large_artifacts_and_resilience.py`

### Prevention rule
> **Rule**: Never expose a model or job as completed before physical artifact publication, checksum verification, and registry indexation are fully committed.

### Reusable lesson
In asynchronous job engines, state visibility must strictly lag artifact durability. Always use the staging-to-commit pattern for large binary payloads.

### Related failures
* [Failure Lesson 05: NetCDF Materialization File Write Omission](./05-netcdf-materialization-file-write-omission.md)
* [Failure Lesson 08: 1GB Large Artifact Streaming & Cloud Run RAM Limits](./08-large-artifact-streaming-and-ram-limits.md)
* [Failure Lesson 11: Artifact Sandbox Push & Server Garbage Collection](./11-artifact-sandbox-push-and-server-garbage-collection.md)
* `JOB-001`: Job State Machine & Cancellation Fencing

---

## Protected Systems & Code References

* `src/marketing_mcp/mcp/tools/artifacts.py`: Artifact materialization and export
* `src/marketing_mcp/storage/metadata.py`: [`MetadataStorage`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/storage/metadata.py)
* `src/marketing_mcp/jobs/executor.py`: Staging, atomic publish, and registry commit sequence
* `tests/unit/test_hard_test_remediation.py`: Artifact immutability and atomic publication tests
