"""Configuration transparency: requested, resolved, and effective configuration audit (T6)."""

from __future__ import annotations

from typing import Any


def build_config_audit(
    requested: dict[str, Any],
    resolved: dict[str, Any],
    effective: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze differences between requested, resolved, and effective model configurations.

    Attributes every setting to its provenance source:
    - 'user_specified': explicitly requested by user
    - 'default_applied': populated by schema defaults
    - 'intelligence_inferred': added by data intelligence engine
    - 'runtime_calibrated': computed at runtime (e.g. scales, coordinate dimensions)
    """
    effective = effective or resolved
    diffs: dict[str, dict[str, Any]] = {}

    all_keys = sorted(set(requested) | set(resolved) | set(effective))

    for key in all_keys:
        req_val = requested.get(key)
        res_val = resolved.get(key)
        eff_val = effective.get(key)

        if key not in requested and key not in resolved:
            attribution = "runtime_calibrated"
            change_type = "runtime_added"
        elif key not in requested:
            attribution = "default_applied"
            change_type = "added_default"
        elif req_val != res_val:
            attribution = "intelligence_inferred"
            change_type = "modified_by_preflight"
        elif res_val != eff_val:
            attribution = "runtime_calibrated"
            change_type = "runtime_scaled"
        else:
            attribution = "user_specified"
            change_type = "retained"

        diffs[key] = {
            "requested": req_val,
            "resolved": res_val,
            "effective": eff_val,
            "attribution": attribution,
            "change_type": change_type,
        }

    return {
        "attributes": diffs,
        "summary": {
            "user_specified_count": sum(1 for d in diffs.values() if d["attribution"] == "user_specified"),
            "default_applied_count": sum(1 for d in diffs.values() if d["attribution"] == "default_applied"),
            "intelligence_inferred_count": sum(1 for d in diffs.values() if d["attribution"] == "intelligence_inferred"),
            "runtime_calibrated_count": sum(1 for d in diffs.values() if d["attribution"] == "runtime_calibrated"),
        },
    }
