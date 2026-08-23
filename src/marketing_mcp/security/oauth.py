"""OAuth 2.1 resource-server token verification (Wave 3 Task 4).

Verifies bearer tokens against the configured authorization server using the
pinned MCP SDK's ``TokenVerifier`` surface. Signature keys come from the
issuer's JWKS; a symmetric secret may be supplied ONLY for explicit private /
test deployments.

Verification failures return ``None`` per the SDK contract — the reason is
never included in responses surfaced to callers.
"""

from __future__ import annotations

from typing import Any

import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

from marketing_mcp.security.policy import SCOPE_CATALOG


class RemoteJWTVerifier(TokenVerifier):
    """Verify OAuth bearer tokens signed by the configured issuer."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        required_scope: str = "marketing:read",
        jwks_client: Any = None,
        symmetric_secret: str | None = None,
        leeway_seconds: int = 30,
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.required_scope = required_scope
        self.leeway = leeway_seconds
        self._secret = symmetric_secret
        self._jwks_client = jwks_client
        if jwks_client is None and symmetric_secret is None:
            from jwt import PyJWKClient

            self._jwks_client = PyJWKClient(f"{self.issuer}/.well-known/jwks.json")

    def _signing_key(self, token: str):
        if self._secret is not None:
            return self._secret
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        try:
            key = self._signing_key(token)
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "HS256"],
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError:
            # Invalid signature, expiry, issuer, audience, or malformed token.
            # Any rejection reason is collapsed to None per the SDK contract.
            return None
        except (KeyError, ValueError):
            return None

        scopes_raw = claims.get("scope") or claims.get("scp") or ""
        if isinstance(scopes_raw, str):
            scopes = scopes_raw.split()
        else:
            scopes = [str(s) for s in scopes_raw]
        if self.required_scope and self.required_scope not in scopes:
            return None
        unknown = set(scopes) - SCOPE_CATALOG - {"*"}
        if unknown:
            return None

        exp = claims.get("exp")
        return AccessToken(
            token=token,
            client_id=str(claims.get("client_id", claims.get("azp", claims["sub"]))),
            scopes=scopes,
            expires_at=int(exp) if exp is not None else None,
            subject=str(claims.get("sub")),
            claims=claims,
        )
