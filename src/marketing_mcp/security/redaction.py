"""Secrets and sensitive data redaction helper.

Recursively scrubs API keys, bearer tokens, passwords, and sensitive headers
from error envelopes, logs, and trace contexts.
"""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_PATTERNS = re.compile(
    r"(?i)(auth|token|jwt|bearer|secret|password|key|credential)"
)

BEARER_PATTERN = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-_.]+", re.IGNORECASE)
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*\b")
API_KEY_PATTERN = re.compile(r"\b(key-[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{16,})\b")

REDACTED_STR = "[REDACTED]"


def redact_string(value: str) -> str:
    """Scrub raw token and key patterns from arbitrary strings."""
    v = BEARER_PATTERN.sub(r"\1[REDACTED]", value)
    v = JWT_PATTERN.sub(REDACTED_STR, v)
    v = API_KEY_PATTERN.sub(REDACTED_STR, v)
    return v


def redact_secrets(data: Any, depth: int = 0, max_depth: int = 10) -> Any:
    """Recursively redact sensitive keys and values from dictionaries, lists, and primitives."""
    if depth > max_depth:
        return data

    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            str_key = str(k)
            if SENSITIVE_KEY_PATTERNS.search(str_key):
                if isinstance(v, dict):
                    cleaned[k] = redact_secrets(v, depth=depth + 1, max_depth=max_depth)
                else:
                    cleaned[k] = REDACTED_STR
            else:
                cleaned[k] = redact_secrets(v, depth=depth + 1, max_depth=max_depth)
        return cleaned

    if isinstance(data, (list, tuple, set, frozenset)):
        scrubbed = [redact_secrets(item, depth=depth + 1, max_depth=max_depth) for item in data]
        if isinstance(data, tuple):
            return tuple(scrubbed)
        if isinstance(data, set):
            return set(scrubbed)
        if isinstance(data, frozenset):
            return frozenset(scrubbed)
        return scrubbed

    if isinstance(data, str):
        return redact_string(data)

    return data


def safe_error_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Sanitize error evidence before attaching to a DomainError envelope."""
    if not evidence:
        return {}
    return redact_secrets(evidence)  # type: ignore[return-value]
