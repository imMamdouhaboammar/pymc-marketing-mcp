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


## Public teaser

Anonymous visitors see a six-section, business-first teaser. The selected role changes the question, required inputs, useful output, and first prompt together; the prompt carries into setup. The preview is explicitly illustrative. Capability and readiness claims link to their canonical documents rather than hard-coded totals or release versions.

The local Claude Desktop snippet shares `.demo-runtime` storage with the CLI sample via `uv --directory`. Replace the absolute project directory. The synthetic sample is MMM data, not customer transaction input for CLV. Statistical fitting and diagnostic approval are not guaranteed.

The public visual contract lives in [DESIGN.md](DESIGN.md); its content brief and claim sources live in [PRODUCT.md](PRODUCT.md). Outfit, Inter, and JetBrains Mono are self-hosted Latin variable fonts from pinned Fontsource packages (OFL-1.1). The public page does not require Google Fonts requests.

### Browser verification

```bash
bun install --frozen-lockfile
bunx playwright install chromium
bun run test:e2e
```

`test:e2e` builds the production client, then tests the built preview. Coverage includes role-specific setup context, keyboard tabs/disclosures, clipboard success/denial, sign-in entry/back, automated WCAG AA checks, 320/390/720/1440px reflow, 200% CSS zoom, loaded font faces, and screenshots. Existing authenticated backend operations require separate credentials and are not covered by these anonymous journeys.

For environments supplying their own Chromium binary, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH`. The standard installation remains the default. Screenshots go to `test-results/review` unless `TEASER_SCREENSHOT_DIR` is supplied.

The production build cleans superseded hashed client JS/CSS after Vite writes a valid index. It preserves existing non-client files in `dist`, which the Python Docker image copies verbatim.
