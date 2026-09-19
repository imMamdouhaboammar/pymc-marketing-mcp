"""Typed user overrides schema and normalization for dataset intelligence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from marketing_mcp.errors import DomainError
from marketing_mcp.intelligence.contracts.semantics import SemanticRole


class UserOverridesInput(BaseModel):
    """Business-facing or column-specific semantic overrides for dataset intelligence."""

    target_column: str | None = Field(
        default=None, description="Primary KPI/outcome column (e.g. 'revenue', 'conversions')"
    )
    date_column: str | None = Field(
        default=None, description="Temporal timestamp or date column"
    )
    channel_columns: list[str] | None = Field(
        default=None, description="Media channel spend columns"
    )
    channels: list[str] | None = Field(
        default=None, description="Alias for channel_columns"
    )
    control_columns: list[str] | None = Field(
        default=None, description="Exogenous control columns"
    )
    controls: list[str] | None = Field(
        default=None, description="Alias for control_columns"
    )
    dims: list[str] | None = Field(
        default=None, description="Panel dimension columns (e.g. ['geo', 'market'])"
    )
    dimension_columns: list[str] | None = Field(
        default=None, description="Alias for dims"
    )
    roles: dict[str, Any] | None = Field(
        default=None, description="Per-column role assignments: {col_name: role_spec}"
    )


def _to_semantic_role(role_val: Any) -> SemanticRole:
    if isinstance(role_val, SemanticRole):
        return role_val
    if isinstance(role_val, str):
        role_lower = role_val.strip().lower()
        # Direct match or map known aliases
        alias_map = {
            "target": SemanticRole.TARGET,
            "kpi": SemanticRole.TARGET,
            "outcome": SemanticRole.TARGET,
            "date": SemanticRole.DATE,
            "time": SemanticRole.DATE,
            "channel": SemanticRole.MEDIA_CHANNEL,
            "media_channel": SemanticRole.MEDIA_CHANNEL,
            "media": SemanticRole.MEDIA_CHANNEL,
            "spend": SemanticRole.MEDIA_CHANNEL,
            "control": SemanticRole.CONTROL,
            "dimension": SemanticRole.DIMENSION,
            "dim": SemanticRole.DIMENSION,
            "geo": SemanticRole.DIMENSION,
            "market": SemanticRole.DIMENSION,
            "identifier": SemanticRole.IDENTIFIER,
            "id": SemanticRole.IDENTIFIER,
        }
        if role_lower in alias_map:
            return alias_map[role_lower]
        try:
            return SemanticRole(role_lower)
        except ValueError:
            return SemanticRole.UNKNOWN
    return SemanticRole.UNKNOWN


def normalize_user_overrides(
    overrides: UserOverridesInput | dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Normalizes typed or untyped user semantic overrides into canonical column-keyed format:

    {column_name: {"role": SemanticRole, ...}}
    Raises DomainError(code="INPUT_INVALID") if input cannot be parsed.
    """
    if overrides is None:
        return {}

    raw: dict[str, Any]
    if isinstance(overrides, UserOverridesInput):
        raw = overrides.model_dump(exclude_none=True)
    elif isinstance(overrides, dict):
        raw = dict(overrides)
    else:
        raise DomainError(
            "INPUT_INVALID",
            f"user_overrides must be a dictionary or UserOverridesInput, got {type(overrides).__name__}",
            next_action="Provide a dictionary with target_column, channels, roles, or column-keyed overrides",
        )

    normalized: dict[str, dict[str, Any]] = {}

    # 1. Handle canonical top-level fields
    # target_column
    if "target_column" in raw:
        tgt = raw.pop("target_column")
        if tgt is not None:
            if not isinstance(tgt, str):
                raise DomainError(
                    "INPUT_INVALID",
                    f"'target_column' override must be a string column name, got {type(tgt).__name__}",
                    evidence={"target_column": str(tgt)},
                    next_action="Specify target_column as a single column name string (e.g. 'revenue_usd')",
                )
            normalized[tgt] = {"role": SemanticRole.TARGET}

    # date_column
    if "date_column" in raw:
        dt = raw.pop("date_column")
        if dt is not None:
            if not isinstance(dt, str):
                raise DomainError(
                    "INPUT_INVALID",
                    f"'date_column' override must be a string column name, got {type(dt).__name__}",
                    evidence={"date_column": str(dt)},
                    next_action="Specify date_column as a single column name string",
                )
            normalized[dt] = {"role": SemanticRole.DATE}

    # channel_columns / channels
    for ch_key in ("channel_columns", "channels"):
        if ch_key in raw:
            chs = raw.pop(ch_key)
            if chs is not None:
                if not isinstance(chs, (list, tuple)):
                    raise DomainError(
                        "INPUT_INVALID",
                        f"'{ch_key}' override must be a list of column names, got {type(chs).__name__}",
                        evidence={ch_key: str(chs)},
                        next_action=f"Specify {ch_key} as a list of strings",
                    )
                for ch in chs:
                    if not isinstance(ch, str):
                        raise DomainError(
                            "INPUT_INVALID",
                            f"Elements in '{ch_key}' must be string column names, got {type(ch).__name__}",
                            evidence={ch_key: str(chs)},
                            next_action=f"Ensure all items in {ch_key} are string column names",
                        )
                    normalized[ch] = {"role": SemanticRole.MEDIA_CHANNEL}

    # control_columns / controls
    for ctrl_key in ("control_columns", "controls"):
        if ctrl_key in raw:
            ctrls = raw.pop(ctrl_key)
            if ctrls is not None:
                if not isinstance(ctrls, (list, tuple)):
                    raise DomainError(
                        "INPUT_INVALID",
                        f"'{ctrl_key}' override must be a list of column names, got {type(ctrls).__name__}",
                        evidence={ctrl_key: str(ctrls)},
                        next_action=f"Specify {ctrl_key} as a list of strings",
                    )
                for ctrl in ctrls:
                    if not isinstance(ctrl, str):
                        raise DomainError(
                            "INPUT_INVALID",
                            f"Elements in '{ctrl_key}' must be string column names, got {type(ctrl).__name__}",
                            evidence={ctrl_key: str(ctrls)},
                            next_action=f"Ensure all items in {ctrl_key} are string column names",
                        )
                    normalized[ctrl] = {"role": SemanticRole.CONTROL}

    # dims / dimension_columns
    for dim_key in ("dims", "dimension_columns"):
        if dim_key in raw:
            dims = raw.pop(dim_key)
            if dims is not None:
                if not isinstance(dims, (list, tuple)):
                    raise DomainError(
                        "INPUT_INVALID",
                        f"'{dim_key}' override must be a list of column names, got {type(dims).__name__}",
                        evidence={dim_key: str(dims)},
                        next_action=f"Specify {dim_key} as a list of strings",
                    )
                for dim in dims:
                    if not isinstance(dim, str):
                        raise DomainError(
                            "INPUT_INVALID",
                            f"Elements in '{dim_key}' must be string column names, got {type(dim).__name__}",
                            evidence={dim_key: str(dims)},
                            next_action=f"Ensure all items in {dim_key} are string column names",
                        )
                    normalized[dim] = {"role": SemanticRole.DIMENSION}

    # roles dict
    if "roles" in raw:
        roles_val = raw.pop("roles")
        if roles_val is not None:
            if not isinstance(roles_val, dict):
                raise DomainError(
                    "INPUT_INVALID",
                    f"'roles' override must be a dictionary mapping column names to roles, got {type(roles_val).__name__}",
                    evidence={"roles": str(roles_val)},
                    next_action="Provide roles as a dictionary, e.g. {'revenue': 'target', 'tv': 'media_channel'}",
                )
            for col, r_spec in roles_val.items():
                if isinstance(r_spec, dict):
                    normalized[col] = {
                        "role": _to_semantic_role(r_spec.get("role")),
                        "semantic_type": r_spec.get("semantic_type"),
                        "currency": r_spec.get("currency"),
                    }
                elif isinstance(r_spec, (str, SemanticRole)):
                    normalized[col] = {"role": _to_semantic_role(r_spec)}
                else:
                    raise DomainError(
                        "INPUT_INVALID",
                        f"Role specification for column '{col}' must be a string or dict, got {type(r_spec).__name__}",
                        evidence={"column": col, "spec": str(r_spec)},
                        next_action="Provide role as string or {'role': 'target'}",
                    )

    # 2. Handle remaining column-keyed entries in raw
    for col, spec in raw.items():
        if isinstance(spec, dict):
            normalized[col] = {
                "role": _to_semantic_role(spec.get("role")),
                "semantic_type": spec.get("semantic_type"),
                "currency": spec.get("currency"),
            }
        elif isinstance(spec, (str, SemanticRole)):
            normalized[col] = {"role": _to_semantic_role(spec)}
        else:
            raise DomainError(
                "INPUT_INVALID",
                f"Override for column '{col}' must be a role string or dictionary, got {type(spec).__name__}",
                evidence={"column": col, "value": str(spec)},
                next_action="Use {'role': 'target'} or 'target'",
            )

    return normalized


__all__ = ["UserOverridesInput", "normalize_user_overrides"]
