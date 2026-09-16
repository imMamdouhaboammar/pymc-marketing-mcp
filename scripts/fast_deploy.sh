#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# PyMC Marketing MCP - Fast Deploy to Google Cloud Run
# One-Command Serverless Bayesian Marketing Science Engine
# ==============================================================================

export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:-datacloud.antigravity}"

# Colors for output
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BOLD}${BLUE}===================================================================${NC}"
echo -e "${BOLD}${BLUE}   PyMC Marketing MCP - Fast Deploy to Google Cloud Run            ${NC}"
echo -e "${BOLD}${BLUE}===================================================================${NC}"

# Source .env if available
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
elif [ -f "../.env" ]; then
    set -a
    source ../.env
    set +a
fi

# 1. Preflight: gcloud check
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: 'gcloud' CLI is not installed or not in PATH.${NC}" >&2
    echo "Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install" >&2
    exit 1
fi

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"
if [ -z "${PROJECT_ID}" ]; then
    echo -e "${YELLOW}No active GCP project detected.${NC}"
    read -r -p "Enter your Google Cloud Project ID: " INPUT_PROJECT
    PROJECT_ID="${INPUT_PROJECT}"
    if [ -z "${PROJECT_ID}" ]; then
        echo -e "${RED}Error: Project ID is required to proceed.${NC}" >&2
        exit 1
    fi
    gcloud config set project "${PROJECT_ID}"
fi

REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${GCP_SERVICE_NAME:-pymc-marketing-mcp}"
REPO_NAME="${GCP_REPO_NAME:-mcp-servers}"
BUCKET_NAME="${GCS_BUCKET_NAME:-${PROJECT_ID}-pymc-mcp-artifacts}"

# Deploy Mode: beta (unauthenticated) or secure (API key)
DEPLOY_MODE="${1:-${DEPLOY_MODE:-beta}}"
AUTH_ENABLED="false"
ALLOW_ANONYMOUS="true"
API_KEY="${MARKETING_MCP_API_KEY:-}"

if [ "${DEPLOY_MODE}" = "secure" ] || [ "${DEPLOY_MODE}" = "--secure" ]; then
    AUTH_ENABLED="true"
    ALLOW_ANONYMOUS="false"
    if [ -z "${API_KEY}" ]; then
        API_KEY="mcp_$(openssl rand -hex 24 2>/dev/null || python3 -c 'import secrets; print(secrets.token_hex(24))')"
        echo -e "${YELLOW}Generated new secure API Key:${NC} ${BOLD}${API_KEY}${NC}"
    fi
fi

APP_VERSION="$(python3 -c 'import marketing_mcp; print(marketing_mcp.__version__)' 2>/dev/null || echo '0.4.0')"
GIT_SHA="$(git rev-parse --short=8 HEAD 2>/dev/null || echo 'dev')"
IMAGE_TAG="${APP_VERSION}-${GIT_SHA}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

echo -e "Project:        ${GREEN}${PROJECT_ID}${NC}"
echo -e "Region:         ${GREEN}${REGION}${NC}"
echo -e "Service Name:   ${GREEN}${SERVICE_NAME}${NC}"
echo -e "Storage Bucket: ${GREEN}gs://${BUCKET_NAME}${NC}"
echo -e "Mode:           ${GREEN}${DEPLOY_MODE}${NC} (Auth: ${AUTH_ENABLED})"
echo -e "Image URI:      ${BLUE}${IMAGE_URI}${NC}"
echo -e "-------------------------------------------------------------------"

# 2. Enable Required APIs
echo -e "${BLUE}==> [1/5] Ensuring required Google Cloud APIs are enabled...${NC}"
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    storage.googleapis.com > /dev/null

# 3. Artifact Registry
echo -e "${BLUE}==> [2/5] Checking Artifact Registry repository...${NC}"
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" >/dev/null 2>&1; then
    echo "Creating Artifact Registry repository '${REPO_NAME}'..."
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Docker repository for PyMC Marketing MCP" > /dev/null
fi

# 4. GCS Storage Bucket for Model Artifacts
echo -e "${BLUE}==> [3/5] Checking Cloud Storage persistence bucket...${NC}"
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    echo "Creating GCS persistence bucket 'gs://${BUCKET_NAME}'..."
    gcloud storage buckets create "gs://${BUCKET_NAME}" \
        --location="${REGION}" \
        --uniform-bucket-level-access > /dev/null
fi

# 5. Build Image via Cloud Build
echo -e "${BLUE}==> [4/5] Building container image via Google Cloud Build...${NC}"
gcloud builds submit --tag "${IMAGE_URI}" . --quiet

# 6. Deploy to Cloud Run
echo -e "${BLUE}==> [5/5] Deploying service to Google Cloud Run...${NC}"
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_URI}" \
    --region "${REGION}" \
    --platform managed \
    --cpu 4 \
    --memory 8Gi \
    --timeout 1800 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 2 \
    --no-cpu-throttling \
    --execution-environment gen2 \
    --port 8080 \
    --set-env-vars "MARKETING_MCP_DATA_DIR=/var/lib/marketing-mcp/data,MARKETING_MCP_INGEST_DIR=/var/lib/marketing-mcp/inbox,MARKETING_MCP_ARTIFACT_DIR=/var/lib/marketing-mcp/artifacts,MARKETING_MCP_METADATA_DB=/var/lib/marketing-mcp-local/metadata.db,MARKETING_MCP_TRANSPORT=streamable-http,MARKETING_MCP_API_KEY=${API_KEY},MARKETING_MCP_AUTH_ENABLED=${AUTH_ENABLED},MARKETING_MCP_ALLOW_ANONYMOUS_HTTP=${ALLOW_ANONYMOUS}" \
    --add-volume "name=mcp-storage,type=cloud-storage,bucket=${BUCKET_NAME}" \
    --add-volume-mount "volume=mcp-storage,mount-path=/var/lib/marketing-mcp" \
    --allow-unauthenticated \
    --quiet

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')"

echo ""
echo -e "${BOLD}${GREEN}===================================================================${NC}"
echo -e "${BOLD}${GREEN}   DEPLOYMENT COMPLETE! PyMC Marketing MCP is Live!               ${NC}"
echo -e "${BOLD}${GREEN}===================================================================${NC}"
echo -e " Base URL:        ${BOLD}${SERVICE_URL}${NC}"
echo -e " Remote MCP URL:  ${BOLD}${SERVICE_URL}/mcp${NC}"
echo -e " Health Endpoint: ${BOLD}${SERVICE_URL}/health${NC}"
echo -e " Auth Enabled:    ${AUTH_ENABLED}"
if [ "${AUTH_ENABLED}" = "true" ]; then
    echo -e " API Key:         ${BOLD}${API_KEY}${NC}"
fi
echo -e "==================================================================="
echo ""
echo -e "${BOLD}Client Configuration Snippets:${NC}"
echo ""
if [ "${AUTH_ENABLED}" = "true" ]; then
echo -e "${BOLD}1. Claude Desktop / Cursor / Antigravity (~/.cursor/mcp.json or claude_desktop_config.json):${NC}"
cat << EOF
{
  "mcpServers": {
    "pymc-marketing": {
      "url": "${SERVICE_URL}/mcp",
      "headers": {
        "Authorization": "Bearer ${API_KEY}"
      }
    }
  }
}
EOF
echo ""
echo -e "${BOLD}2. Claude Code CLI:${NC}"
echo "  claude mcp add pymc-marketing ${SERVICE_URL}/mcp --header \"Authorization: Bearer ${API_KEY}\""
else
echo -e "${BOLD}1. Claude Desktop / Cursor / Antigravity (~/.cursor/mcp.json or claude_desktop_config.json):${NC}"
cat << EOF
{
  "mcpServers": {
    "pymc-marketing": {
      "url": "${SERVICE_URL}/mcp"
    }
  }
}
EOF
echo ""
echo -e "${BOLD}2. Claude Code CLI:${NC}"
echo "  claude mcp add pymc-marketing ${SERVICE_URL}/mcp"
fi

echo ""
echo -e "${BOLD}3. Quick Health Check:${NC}"
echo "  curl -sS ${SERVICE_URL}/health | jq ."
echo ""
