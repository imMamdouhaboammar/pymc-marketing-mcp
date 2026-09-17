"""Standardized marketing intelligence issues and severity classifications."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    BLOCKING = "blocking"


class IssueCode(str, Enum):
    MIXED_CONVERSION_SEMANTICS = "MIXED_CONVERSION_SEMANTICS"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    ATTRIBUTED_REVENUE_TARGET = "ATTRIBUTED_REVENUE_TARGET"
    CURRENCY_INCONSISTENCY = "CURRENCY_INCONSISTENCY"
    STAGGERED_CHANNEL_LIFECYCLE = "STAGGERED_CHANNEL_LIFECYCLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    SPARSE_CHANNEL = "SPARSE_CHANNEL"
    LOW_VARIATION_CHANNEL = "LOW_VARIATION_CHANNEL"
    HIGH_CHANNEL_COLLINEARITY = "HIGH_CHANNEL_COLLINEARITY"
    MARKET_HETEROGENEITY = "MARKET_HETEROGENEITY"
    TRACKING_DISCONTINUITY = "TRACKING_DISCONTINUITY"
    POSSIBLE_TARGET_TRACKING_GAP = "POSSIBLE_TARGET_TRACKING_GAP"
    NON_RECTANGULAR_PANEL = "NON_RECTANGULAR_PANEL"
    EXTREME_OUTLIERS = "EXTREME_OUTLIERS"
    MISSING_DATE_COLUMN = "MISSING_DATE_COLUMN"
    MISSING_TARGET_COLUMN = "MISSING_TARGET_COLUMN"
    MISSING_CHANNEL_COLUMNS = "MISSING_CHANNEL_COLUMNS"
    IRREGULAR_TIME_SERIES = "IRREGULAR_TIME_SERIES"
    HIGH_MISSINGNESS = "HIGH_MISSINGNESS"
    NEGATIVE_MEDIA_SPEND = "NEGATIVE_MEDIA_SPEND"
    DUPLICATE_PERIOD = "DUPLICATE_PERIOD"


class IntelligenceIssue(BaseModel):
    code: IssueCode = Field(description="Standardized issue code")
    severity: IssueSeverity = Field(description="Severity level: info, warning, high, blocking")
    summary: str = Field(description="Actionable summary of the issue")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Structured diagnostic evidence")
    affected_columns: list[str] = Field(default_factory=list, description="Columns related to this issue")
    affected_rows: int | None = Field(default=None, description="Number of rows impacted if applicable")
    why_it_matters: str = Field(description="Domain explanation of statistical or business consequence")
    recommended_action: str = Field(description="Concrete remediation step for user or agent")
    blocking: bool = Field(default=False, description="True if this issue blocks automated model fitting")
