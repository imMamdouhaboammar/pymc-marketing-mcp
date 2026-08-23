from __future__ import annotations

import argparse
import os
import sys

from marketing_mcp.auth import AuthManager, create_jwt_token, generate_api_key


def main():
    parser = argparse.ArgumentParser(
        prog="marketing-mcp-auth",
        description="PyMC Marketing MCP Authentication & Token Management Utility",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Command: generate-api-key
    p_apikey = subparsers.add_parser("generate-api-key", help="Generate a new secure API Key")
    p_apikey.add_argument(
        "--prefix", default="mcp_live_", help="Prefix for the key (default: mcp_live_)"
    )

    # Command: mint-jwt
    p_jwt = subparsers.add_parser("mint-jwt", help="Mint a signed JWT Bearer token")
    p_jwt.add_argument(
        "--secret", default=None, help="JWT secret key (or reads MARKETING_MCP_JWT_SECRET)"
    )
    p_jwt.add_argument("--client-id", default="claude-desktop", help="Client / Subject ID")
    p_jwt.add_argument(
        "--days", type=int, default=365, help="Token validity in days (default: 365)"
    )
    p_jwt.add_argument("--scopes", nargs="*", default=["*"], help="Granted permission scopes")

    # Command: verify
    p_verify = subparsers.add_parser("verify", help="Verify an API Key or JWT token")
    p_verify.add_argument("token", help="The token or API key to verify")

    args = parser.parse_args()

    if args.command == "generate-api-key":
        key = generate_api_key(prefix=args.prefix)
        print("Generated API Key:")
        print(f"  {key}\n")
        print("To enable this key in Cloud Run / Environment:")
        print(f'  export MARKETING_MCP_API_KEY="{key}"')

    elif args.command == "mint-jwt":
        secret = args.secret or os.getenv("MARKETING_MCP_JWT_SECRET")
        if not secret:
            print(
                "Error: JWT secret is required. Pass --secret or set MARKETING_MCP_JWT_SECRET",
                file=sys.stderr,
            )
            sys.exit(1)
        token = create_jwt_token(
            secret=secret,
            client_id=args.client_id,
            scopes=args.scopes,
            expires_in_seconds=args.days * 86400,
        )
        print(f"Generated JWT Bearer Token (Valid for {args.days} days for '{args.client_id}'):")
        print(f"  {token}\n")
        print("Client Header Configuration:")
        print(f"  Authorization: Bearer {token}")

    elif args.command == "verify":
        auth_mgr = AuthManager.from_env()
        from starlette.datastructures import Headers, QueryParams

        headers = Headers({"authorization": f"Bearer {args.token}"})
        ctx = auth_mgr.authenticate(headers, QueryParams())
        if ctx.authenticated:
            print("Authentication Successful!")
            print(f"  Auth Type: {ctx.auth_type}")
            print(f"  Client ID: {ctx.client_id}")
            print(f"  Scopes:    {ctx.scopes}")
        else:
            print(f"Authentication Failed: {ctx.error_message}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
