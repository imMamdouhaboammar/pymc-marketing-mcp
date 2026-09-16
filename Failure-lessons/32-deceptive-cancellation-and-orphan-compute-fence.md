# Failure Lesson 32 — Deceptive Cancellation & Orphan Compute Fences

**Date Encountered**: 2026-09-16  
**Component**: `marketing_mcp/mcp/tools/jobs.py`, `marketing_mcp/jobs/executor.py`, `marketing_mcp/jobs/process_worker.py`, `crates/marketing_mcp_fast/src/engine.rs`  
**Severity**: High (Compute Resource Leak / Deceptive API Semantics / Runaway Resource Consumption)  
**Impact Area**: Background MCMC Sampling Jobs / Asynchronous Task Cancellation / Worker Process Fences  

---

## 1. Executive Summary

When an AI client or user requested cancellation of an ongoing asynchronous job (e.g. `fit_mmm`), the API promptly returned an envelope indicating the job was `cancelled` or `cancelling`. However, because PyMC sampling was executed inside an executor thread (`loop.run_in_executor`), cancelling the enclosing asyncio Task did not terminate the underlying OS thread.

The Python worker continued sampling MCMC chains to completion for minutes or hours in the background—consuming CPU cores, RAM, and thermals—only to discard the final result when attempting to write to the database.

---

## 2. Root Cause Analysis

1. **Asyncio CancelledError vs. Thread Boundary**: In Python's asyncio runtime, cancelling a task awaiting `loop.run_in_executor` raises `asyncio.CancelledError` inside the coroutine, but leaves the target callable executing undisturbed in the thread pool.
2. **Missing Cooperative Cancellation Checks**: Background job runners (`_fit_runner`, `_resume_runner`) did not check whether `cancel_event.is_set()` before launching heavy PyMC sampling or between successive checkpoint stages (`sampling_initialized`, `posterior_saved`, `diagnostics_completed`).
3. **Absence of Fast Native Cancellation Acknowledgment**: The client had no lightweight, sub-millisecond receipt confirming that the cancellation intent had tripped the execution fence.

---

## 3. Resolution & Hardening

1. **Native Cancellation Acknowledgment (`fast_acknowledge_cancellation`)**:
   - Implemented `acknowledge_job_cancellation` in native Rust (with pure Python fallback).
   - Generates immediate structured acknowledgment (`acknowledged: true`, `fence_triggered: true`, `status: "cancelled"|"cancelling"`).
2. **Cooperative Cancellation Fence in Job Runners**:
   - Hardened `_fit_runner` and `_resume_runner` in `marketing_mcp/mcp/tools/jobs.py` with defensive cancellation checks (`if cancel_event.is_set(): raise asyncio.CancelledError()`) before and after each expensive phase and checkpoint.
   - Prevents recording checkpoints or committing posterior artifacts if cancellation occurred during execution.
3. **Fenced Lease Validation in Repository**:
   - `finish_claim` strictly rejects attempts by workers to publish `SUCCEEDED` results if the job transitioned to `CANCELLING` or if the fencing token expired.

---

## 4. Architectural Invariants Established

1. **Truthful Cancellation Invariant**: Cancelling an asynchronous job must trigger active compute termination; deceptive cancellation where client-facing state is marked cancelled while background threads continue running is strictly prohibited.
2. **Cooperative Checkpoint Fence Invariant**: Every intermediate checkpoint and stage transition in a long-running job runner must evaluate the cancellation token and abort before scheduling further work.
