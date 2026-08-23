# Google Cloud Run Deployment Guide

This document outlines the production architecture and deployment instructions for running **PyMC Marketing MCP** on **Google Cloud Run**.

---

## 1. Architecture Overview

```text
AI Agent Client (Claude / Cursor / Web App)
       │
       ▼ (Streamable HTTP / SSE: POST/GET https://<service-url>/mcp)
┌─────────────────────────────────────────────────────────────┐
│ Google Cloud Run (Serverless Container)                     │
│                                                             │
│  - 4 vCPUs (Dedicated, no CPU throttling)                   │
│  - 8 GiB RAM (High-throughput Bayesian sampling)             │
│  - Execution Environment: Gen 2                              │
│  - Timeout: 1800s (30 mins for MCMC sampling)               │
│  - Concurrency: 1 | Max Instances: 1                        │
│                                                             │
│  Container (/app):                                          │
│    marketing-mcp --transport streamable-http                │
│    Uvicorn ASGI Engine (Starlette + MCP 2.0.0 SDK)          │
│                                                             │
│  Mounted Volume (/var/lib/marketing-mcp):                   │
│    ├── data/       (Raw CSV/Parquet datasets)               │
│    ├── artifacts/  (NetCDF .nc fitted models & plots)       │
│    ├── inbox/      (Ingestion staging)                      │
│    └── metadata.db (SQLite provenance & diagnostics ledger) │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Cloud Storage FUSE Mount)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ Google Cloud Storage Bucket (gs://pymc-marketing-storage)   │
│  - Persistent Model Weights (.nc)                           │
│  - Versioned Experiment History & Diagnostics Ledger        │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Key Optimization Parameters

| Parameter | Recommended Setting | Rationale |
| :--- | :--- | :--- |
| **CPU** | `4 vCPU` | PyMC NUTS sampler runs multi-chain sampling concurrently. |
| **Memory** | `8 GiB` | ArviZ `InferenceData` xarray graphs require adequate RAM for large posterior draws. |
| **Timeout** | `1800` (30 mins) | Bayesian MCMC fitting (`fit_mmm`, `cross_validate_mmm`) requires more than standard 5m web timeouts. |
| **CPU Throttling** | `--no-cpu-throttling` | Keeps CPU always allocated during MCMC processing without throttling. |
| **Concurrency** | `80` | Allows concurrent SSE streaming connections and JSON-RPC tool calls without blocking. |
| **Max Instances** | `1` | Prevents multiple containers from modifying SQLite metadata simultaneously. |
| **Execution Env** | `gen2` | Second-generation execution environment provides full Linux kernel compatibility and fast filesystem I/O. |
| **Authentication** | `API Key / JWT` | Dual-mode auth middleware protecting endpoints via Bearer headers, X-API-Key, or Query params. |

---

## 3. Authentication & Key Management

The server features a built-in cryptographic authentication subsystem:
* **API Key Auth**: High-entropy keys prefixed with `mcp_live_...` validated in constant-time.
* **JWT Bearer Auth**: Signed HS256 tokens with configurable expiration, claims, and permission scopes.
* **Header-Only Credentials**: Credentials are accepted exclusively via `Authorization: Bearer <TOKEN>` or `X-API-Key` headers. Query-string credentials (`?token=` / `?api_key=`) are rejected because URLs leak through proxy and browser logs.
* **Public Endpoints**: `/health` and `/` remain open for load balancers and health probes.

### Generating & Managing Keys via CLI
```bash
# Generate a new API Key
marketing-mcp-auth generate-api-key

# Mint a 365-day signed JWT Bearer token
marketing-mcp-auth mint-jwt --secret "YOUR_JWT_SECRET" --client-id "claude-desktop" --days 365

# Verify an existing token or API key
marketing-mcp-auth verify "mcp_live_..."
```

---

## 4. One-Command Automated Deployment

Run the included automated deployment script:

```bash
# Export custom variables if needed (defaults to active gcloud config)
export GCP_PROJECT_ID="project-10698895-5ed8-4764-bb7"
export GCP_REGION="us-central1"

./scripts/deploy_cloud_run.sh
```

---

## 5. Client Configuration & Integration

### Claude Desktop (`claude_desktop_config.json`) / Antigravity / Cursor
```json
{
  "mcpServers": {
    "pymc-marketing": {
      "url": "https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

### Claude Code (CLI)
```bash
claude mcp add pymc-marketing https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp --header "Authorization: Bearer YOUR_API_KEY_HERE"
```

### OpenAI Codex / Stdio-Only Clients (via mcp-remote bridge)
```json
{
  "mcpServers": {
    "pymc-marketing": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp",
        "--header",
        "Authorization: Bearer YOUR_API_KEY_HERE"
      ]
    }
  }
}
```

### Python / Gemini / Custom AI Agents (LangChain, LangGraph, LlamaIndex)
```python
import asyncio
import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    url = "https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp"
    api_key = "YOUR_API_KEY_HERE"
    headers = {"Authorization": f"Bearer {api_key}"}

    async with (
        httpx2.AsyncClient(headers=headers) as http_client,
        streamable_http_client(url, http_client=http_client) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        print(f"Connected! Available tools: {len(tools.tools)}")

asyncio.run(main())
```

---

## 6. Verification Endpoints
* **Health Check**: `GET https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/health`
* **MCP SSE Endpoint**: `POST/GET https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp`

