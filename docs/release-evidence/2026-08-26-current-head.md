# Release evidence — `cb1d75d1fb82add77bb17f0c5903b9dab02c54a6`

<!-- GENERATED FILE - machine-collected release evidence. Do not hand-edit results. -->

This report is machine-collected: every row below records a command that was executed and the exit code it returned. Hand-edited pass/fail claims are not release evidence.

- **Verdict:** PASS
- **Commit:** `cb1d75d1fb82add77bb17f0c5903b9dab02c54a6`
- **Collected at:** 2026-08-26T11:23:48Z
- **Collected on:** local workstation
- **Application version:** 0.4.0
- **Platform:** Darwin 25.5.0 (arm64), CPython 3.12.13

## Dependency versions

| Package | Version |
|---|---|
| `pymc-marketing` | 1.0.0 |
| `pymc` | 6.0.1 |
| `arviz` | 1.3.0 |
| `mcp` | 2.0.0 |
| `pydantic` | 2.12.5 |
| `xarray` | 2026.7.0 |
| `numpy` | 2.4.6 |
| `pandas` | 2.3.3 |
| `h5netcdf` | 1.8.1 |

## Executed commands

| Command | Exit code | Passed | Failed | Skipped | Output tail |
|---|---|---|---|---|---|
| `uv run pytest -n auto -q -m "not statistical"` | 0 | 413 | 0 | 0 | 413 passed, 38 warnings in 27.21s |
| `uv run ruff check src tests scripts` | 0 | - | - | - | All checks passed! |
| `uv run python scripts/generate_capability_inventory.py --check` | 0 | - | - | - | /Users/mamdouhaboammar/Downloads/pymc-marketing-mcp-v0.2.0/docs/CAPABILITIES.md matches the capability registry (39 capabilities) |
| `uv build` | 0 | - | - | - | Successfully built dist/pymc_marketing_mcp-0.4.0-py3-none-any.whl |

## Build artifacts

| Artifact | Bytes | SHA-256 |
|---|---|---|
| `pymc_marketing_mcp-0.4.0-py3-none-any.whl` | 125236 | `5f4b3fe036c06b76748dc1c0cac1a0601c3ee1d4414481f8d5a08170507e9b87` |
| `pymc_marketing_mcp-0.4.0.tar.gz` | 264230 | `be2f22587c33e981983170e581d2a6df31c8972b1428271fe565b95fafd08e9f` |
