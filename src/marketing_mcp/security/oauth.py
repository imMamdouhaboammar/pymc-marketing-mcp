"""OAuth 2.1 resource-server token verification."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

from marketing_mcp.security.policy import SCOPE_CATALOG

_ASYMMETRIC_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)


class RemoteJWTVerifier(TokenVerifier):
    """Verify externally issued bearer tokens with trusted issuer configuration."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        required_scope: str | None = "marketing:read",
        *,
        required_scopes: Sequence[str] | None = None,
        jwks_url: str | None = None,
        algorithms: Sequence[str] | None = None,
        tenant_claim: str = "tenant_id",
        require_tenant: bool = False,
        jwks_client: Any = None,
        symmetric_secret: str | None = None,
        leeway_seconds: int = 30,
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        self.required_scopes = tuple(
            required_scopes if required_scopes is not None else ([required_scope] if required_scope else [])
        )
        self.required_scope = self.required_scopes[0] if self.required_scopes else ""
        self.tenant_claim = tenant_claim
        self.require_tenant = require_tenant
        self.leeway = leeway_seconds
        self._secret = symmetric_secret
        self.jwks_url = jwks_url or f"{self.issuer}/.well-known/jwks.json"
        selected_algorithms = algorithms or (["HS256"] if symmetric_secret is not None else ["RS256"])
        if symmetric_secret is None and not set(selected_algorithms) <= _ASYMMETRIC_ALGORITHMS:
            raise ValueError("Remote JWKS verification requires asymmetric signing algorithms")
        if symmetric_secret is not None and set(selected_algorithms) != {"HS256"}:
            raise ValueError("Explicit symmetric verification supports HS256 only")
        self.algorithms = tuple(selected_algorithms)
        self._jwks_client = jwks_client
        if jwks_client is None and symmetric_secret is None:
            from jwt import PyJWKClient

            self._jwks_client = PyJWKClient(self.jwks_url)

    def _signing_key(self, token: str):
        if self._secret is not None:
            return self._secret
        return self._jwks_client.get_signing_key_from_jwt(token).key

    def verify(self, token: str) -> AccessToken | None:
        """Synchronously verify a token for the application's Starlette middleware."""
        if not token:
            return None
        try:
            claims = jwt.decode(
                token,
                self._signing_key(token),
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except (jwt.PyJWTError, KeyError, OSError, TypeError, ValueError):
            return None

        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            return None

        scopes_raw = claims.get("scope") or claims.get("scp") or ""
        if isinstance(scopes_raw, str):
            scopes = scopes_raw.split()
        elif isinstance(scopes_raw, list):
            scopes = [str(scope) for scope in scopes_raw]
        else:
            return None
        if any(scope not in scopes for scope in self.required_scopes):
            return None
        if set(scopes) - SCOPE_CATALOG:
            return None

        tenant_id = claims.get(self.tenant_claim)
        if self.require_tenant and (not isinstance(tenant_id, str) or not tenant_id.strip()):
            return None

        return AccessToken(
            token=token,
            client_id=subject,
            scopes=scopes,
            expires_at=int(claims["exp"]),
            subject=subject,
            claims=claims,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        """Implement the installed MCP SDK's asynchronous TokenVerifier contract."""
        return self.verify(token)
