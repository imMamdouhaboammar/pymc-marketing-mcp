# Failure Lesson 15: Universal MCP Agent Transport Interop (ChatGPT, Claude, Codex, Gemini)

## 1. Executive Summary & Context
- **Component**: `src/marketing_mcp/cli.py`, `src/marketing_mcp/auth.py`
- **Severity**: High (Connectivity Blocker for AI Agent Ecosystem)
- **Symptom**: Cloud AI sandboxes (such as ChatGPT Developer MCP and external remote agents) failed to connect with:
  `FORBIDDEN: This conversation does not support developer MCPs`

## 2. Root Cause Analysis
1. Remote AI runtime agents (ChatGPT, Codex web clients, Gemini cloud agents) cannot spawn local subprocesses via `stdio`. They connect strictly over **Streamable HTTP / SSE transports** against publicly reachable endpoints.
2. AI client connectors inspect standard discovery metadata. In the absence of an explicit `/.well-known/mcp.json` discovery payload and open public endpoints in the authentication middleware, developer MCP connectors are blocked pre-flight.

## 3. Resolution & Fix
- Added canonical `/.well-known/mcp.json` returning server name, protocol version (`2024-11-05`), available endpoints (`/mcp`, `/health`), and transport capabilities.
- Added `/.well-known/mcp.json` to the default `public_paths` whitelist in `MCPAuthMiddleware`.
- Maintained strict local stdio support while providing streamlined Streamable-HTTP discovery for all agent clients.

## 4. Verification & Prevention
- Verified via `tests/integration/test_wave0_wave1_universal_and_security.py::test_universal_agent_discovery_endpoint` (PASS).
