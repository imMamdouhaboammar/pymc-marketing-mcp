"""Secrets and sensitive data redaction helper.

Recursively scrubs API keys, bearer tokens, passwords, signed URL signatures,
and sensitive headers from error envelopes, logs, and trace contexts.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any

SENSITIVE_KEY_PATTERNS = re.compile(
    r"(?i)(auth|token|jwt|bearer|secret|password|key|credential|signature|sig)"
)

BEARER_PATTERN = re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9\-_.]+", re.IGNORECASE)
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*\b")
API_KEY_PATTERN = re.compile(r"\b(key-[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{8,})\b")

# Signed URL query parameter signatures (AWS, Google Cloud, Azure, custom HMAC tokens)
SIGNED_URL_PARAM_PATTERN = re.compile(
    r"(?i)([?&](?:X-Amz-Signature|X-Goog-Signature|signature|sig|token|key|api_key|auth|secret)=)[^&\s'\"]+"
)

# Database URI passwords (e.g. postgres://user:pass@host:5432/db)
DB_PASSWORD_PATTERN = re.compile(r"(?i)(://[^:\s/]+:)[^@\s/]+(@)")

# Key-value assignment pairs (e.g., MARKETING_MCP_API_KEY=..., api_key: "...", secret = ...)
KV_SECRET_PATTERN = re.compile(
    r"(?i)\b((?:MARKETING_MCP_API_KEY|api_key|api-key|secret_key|secret|password|access_token|refresh_token)\s*[:=]\s*[\"']?)[^\s\"',;&]{4,}([\"']?)"
)

REDACTED_STR = "[REDACTED]"


def redact_url(url: str) -> str:
    """Scrub query secrets and basic-auth credentials from URLs."""
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
        # Scrub user/password if present
        netloc = parsed.netloc
        if "@" in netloc and ":" in netloc.split("@")[0]:
            user_part, host_part = netloc.split("@", 1)
            username = user_part.split(":", 1)[0]
            netloc = f"{username}:{REDACTED_STR}@{host_part}"

        # Scrub sensitive query parameters
        if parsed.query:
            query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            scrubbed_pairs = []
            for k, v in query_pairs:
                if SENSITIVE_KEY_PATTERNS.search(k):
                    scrubbed_pairs.append((k, REDACTED_STR))
                else:
                    scrubbed_pairs.append((k, v))
            new_query = urllib.parse.urlencode(scrubbed_pairs)
            parsed = parsed._replace(netloc=netloc, query=new_query)
        else:
            parsed = parsed._replace(netloc=netloc)
        return urllib.parse.urlunparse(parsed)
    except Exception:
        # Fallback to regex scrubbing
        return SIGNED_URL_PARAM_PATTERN.sub(r"\1[REDACTED]", url)


def redact_string(value: str) -> str:
    """Scrub raw tokens, passwords, signed URL parameters, and key patterns from strings."""
    v = BEARER_PATTERN.sub(r"\1[REDACTED]", value)
    v = JWT_PATTERN.sub(REDACTED_STR, v)
    v = API_KEY_PATTERN.sub(REDACTED_STR, v)
    v = DB_PASSWORD_PATTERN.sub(r"\1[REDACTED]\2", v)
    v = SIGNED_URL_PARAM_PATTERN.sub(r"\1[REDACTED]", v)
    v = KV_SECRET_PATTERN.sub(r"\1[REDACTED]\2", v)
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


__all__ = [
    "REDACTED_STR",
    "SENSITIVE_KEY_PATTERNS",
    "redact_secrets",
    "redact_string",
    "redact_url",
    "safe_error_evidence",
]

