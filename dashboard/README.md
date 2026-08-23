# PyMC Marketing MCP - Firebase Admin & User Dashboard

A modern, high-performance web portal built with **React 19, TypeScript, Tailwind CSS v4, and Firebase** for managing API keys, user authentication, and monitoring tool invocation metrics on the **PyMC Marketing MCP** server.

---

## 🌟 Features

### 1. User Portal (`My Portal & Keys`)
- **Authentication**: Email/Password and One-Click Google Sign-In powered by Firebase Auth.
- **Cryptographic Key Management**:
  - Generate secure `mcp_live_...` API keys.
  - One-click copy for newly minted secrets.
  - Active / Revoked status tracking and per-key request counters.
- **AI Client Connection Center**:
  - Pre-configured setup snippets for **Claude Desktop**, **Claude Code CLI**, **Cursor / Antigravity / Windsurf**, **OpenAI Codex**, and **Python SDK**.
  - Dynamically injects your active API key and live Cloud Run endpoint.
- **Consumption Metering**:
  - Live metric cards (Total Invocations, Active Keys, Top Tools, Latency).
  - Real-time audit log of executed tools.

### 2. Admin Console (`Admin Console`)
- **Developer Directory**: Overview of all registered accounts, creation dates, and aggregated usage.
- **Global Key Governance**: Audit and revoke API keys across all users.
- **Server Health**: Real-time Google Cloud Run server status.

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

## 🌐 Production Deployment (Firebase Hosting)

```bash
# 1. Build optimized bundle
bun run build

# 2. Deploy to Firebase Hosting
npx -y firebase-tools deploy --only hosting
```
