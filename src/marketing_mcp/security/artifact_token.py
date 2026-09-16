"""Short-lived, single-artifact download tokens with HMAC-SHA256 signature verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


def _get_signing_key() -> bytes:
    key = os.getenv("MARKETING_MCP_TOKEN_SECRET") or os.getenv("MARKETING_MCP_API_KEY") or "default-ephemeral-artifact-secret"
    return hashlib.sha256(key.encode()).digest()


def generate_artifact_download_token(
    *,
    namespace: str,
    digest: str,
    owner: str,
    tenant_id: str | None,
    expires_in_seconds: int = 86400,
) -> str:
    """Generate a tamper-proof HMAC-signed token granting access ONLY to the specified artifact."""
    payload = {
        "ns": namespace,
        "sha": digest,
        "own": owner,
        "tid": tenant_id or "default",
        "exp": int(time.time()) + expires_in_seconds,
    }
    raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    payload_b64 = base64.urlsafe_b64encode(raw_payload).decode().rstrip("=")
    sig = hmac.new(_get_signing_key(), raw_payload, hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def verify_artifact_download_token(
    token: str,
    *,
    expected_namespace: str,
    expected_digest: str,
) -> bool:
    """Verify that the token is valid, unexpired, and explicitly bound to this artifact."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        payload_b64, sig = parts
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        raw_payload = base64.urlsafe_b64decode(payload_b64 + padding)
        expected_sig = hmac.new(_get_signing_key(), raw_payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        data = json.loads(raw_payload)
        if time.time() > data.get("exp", 0):
            return False
        if data.get("ns") != expected_namespace or data.get("sha") != expected_digest:
            return False
        return True
    except Exception:
        return False
