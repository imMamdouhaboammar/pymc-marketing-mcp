# Failure Lesson 18: P1 Silent SQLite Cleanup Syntax Error & Error Swallowing

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/storage/gc.py`
- **Severity**: P1 Storage Reliability (Silent Garbage Collection Failure)
- **Symptom**: `cleanup_server_storage` reported success while never actually removing expired artifact lifecycle rows or unreferenced blobs.

## 2. Root Cause Analysis
- The SQL query was written as:
  ```sql
  WHERE status = exported
  ```
  SQLite interpreted `exported` as a column identifier rather than a string literal (`'exported'`), throwing an `OperationalError: no such column: exported`.
- The exception was silently discarded by:
  ```python
  except Exception:
      pass
  ```
  masking the defect entirely.

## 3. Resolution & Fix
- Fixed the SQL literal: `WHERE status = 'exported'`.
- Captured operational errors into an `errors: list[str]` array in the return report rather than swallowing exceptions.

## 4. Verification & Prevention
- Verified via `tests/unit/test_wave2_fixes.py::test_storage_gc_sql_syntax_fix` (PASS).
