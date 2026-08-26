# PyMC Marketing MCP - Developer & Admin Dashboard

A modern, high-performance web portal built with **React 19, TypeScript, Tailwind CSS, and Bun** for managing API keys, client connection snippets, and monitoring tool invocation metrics on the **PyMC Marketing MCP** server.

---

## 🌟 Features

### 1. User Portal (`My Portal & Keys`)
- **Authentication**: Email/Password and One-Click Google Sign-In powered by Firebase Auth.
- **Backend Credential Control Plane**:
  - Issue cryptographic `mcp_live_...` API keys via backend `/control/credentials` API.
  - Safe one-time secret display upon creation (raw secrets are never stored at rest or retrieved later).
  - List active keys with prefix, scopes, creation dates, and status.
  - Immediate server-side key revocation.
- **AI Client Connection Center**:
  - Pre-configured setup snippets for **Claude Desktop**, **Claude Code CLI**, **Cursor / Antigravity / Windsurf**, **OpenAI Codex**, and **Python SDK**.
  - Dynamically injects your active API key and live server endpoint.
- **Consumption Metering**:
  - Live metric cards (Total Invocations, Active Keys, Top Tools, Latency).
  - Audit log of executed tools.

### 2. Admin Console (`Admin Console`)
- **Developer Directory**: Overview of registered accounts and aggregated usage.
- **Global Key Governance**: Audit and revoke API keys across all tenants.
- **Server Health**: Real-time server status and readiness probes.

---

## 🚀 Quick Start (Local Development)

```bash
# 1. Enter dashboard folder
cd dashboard

# 2. Install dependencies via Bun
bun install

# 3. Start local development server
bun run dev
```

The application will launch at `http://localhost:5173`.

---

## 🌐 Production Build

```bash
# 1. Build optimized bundle
bun run build
```
