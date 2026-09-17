"""Semantic roles, types, and inferred column contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from .evidence import HeuristicConfidence


class SemanticRole(str, Enum):
    DATE = "date"
    TARGET = "target"
    MEDIA_CHANNEL = "media_channel"
    CONTROL = "control"
    DIMENSION = "dimension"
    IDENTIFIER = "identifier"
    CURRENCY = "currency"
    OBJECTIVE = "objective"
    METRIC_IMPRESSION = "metric_impression"
    METRIC_CLICK = "metric_click"
    METADATA = "metadata"
    UNKNOWN = "unknown"


class SemanticType(str, Enum):
    REVENUE = "revenue"
    ORDERS = "orders"
    CONVERSIONS = "conversions"
    SPEND = "spend"
    IMPRESSIONS = "impressions"
    CLICKS = "clicks"
    GEOGRAPHY = "geography"
    PLATFORM = "platform"
    CAMPAIGN = "campaign"
    CUSTOMER_ID = "customer_id"
    TRANSACTION_DATE = "transaction_date"
    FX_RATE = "fx_rate"
    DISCOUNT = "discount"
    PRICE = "price"
    GENERIC_NUMERIC = "generic_numeric"
    GENERIC_CATEGORICAL = "generic_categorical"
    UNKNOWN = "unknown"


class InferredColumn(BaseModel):
    column: str = Field(description="Column name in the dataset")
    role: SemanticRole = Field(description="Functional role of the column")
    semantic_type: str = Field(description="Specific semantic meaning")
    currency: str | None = Field(default=None, description="Inferred currency code if applicable (e.g. USD, SAR)")
    confidence: HeuristicConfidence = Field(description="Heuristic confidence assessment and supporting evidence")
    user_overridden: bool = Field(default=False, description="True if this assignment was provided via explicit user override")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional semantic metadata (e.g. channel platform, objective)")
