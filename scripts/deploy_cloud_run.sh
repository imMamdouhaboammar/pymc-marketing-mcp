#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# PyMC Marketing MCP - Google Cloud Run Deployment Script
# Production-ready Bayesian Marketing Mix Modeling Serverless Deployment
# ==============================================================================

PROJECT_ID="${GCP_PROJECT_ID:-project-10698895-5ed8-4764-bb7}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${GCP_SERVICE_NAME:-pymc-marketing-mcp}"
REPO_NAME="${GCP_REPO_NAME:-mcp-servers}"
APP_VERSION="${APP_VERSION:-$(python3 -c 'import marketing_mcp; print(marketing_mcp.__version__)' 2>/dev/null || echo '0.4.0')}"
GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD 2>/dev/null || echo 'unknown')}"
IMAGE_TAG="${IMAGE_TAG:-${APP_VERSION}-g${GIT_SHA}}"
API_KEY="${MARKETING_MCP_API_KEY:-mcp_live_$(openssl rand -hex 24)}"

echo "=========================================================="
echo " Starting PyMC Marketing MCP Deployment to Google Cloud"
echo " Project:       ${PROJECT_ID}"
echo " Region:        ${REGION}"
echo " Service Name:  ${SERVICE_NAME}"
echo " Storage Bucket: gs://${BUCKET_NAME}"
echo " API Key Auth:  ${API_KEY}"
echo "=========================================================="

# 1. Set active project
echo "--> Setting active GCP project..."
gcloud config set project "${PROJECT_ID}"

# 2. Enable necessary APIs
echo "--> Verifying enabled GCP services..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    storage.googleapis.com

# 3. Create Artifact Registry repository if it doesn't exist
echo "--> Ensuring Artifact Registry repository '${REPO_NAME}' exists..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="MCP Servers Docker Repository"
fi

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"

# 4. Create GCS Bucket for Model Artifacts and storage persistence if not exists
echo "--> Ensuring Cloud Storage bucket 'gs://${BUCKET_NAME}' exists..."
if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${BUCKET_NAME}" \
        --location="${REGION}" \
        --uniform-bucket-level-access
fi

# 5. Build and submit container image via Cloud Build
echo "--> Building container image via Google Cloud Build..."
gcloud builds submit --tag "${IMAGE_URI}" .

# 6. Deploy to Cloud Run with optimal MCMC and Bayesian compute settings
echo "--> Deploying service to Google Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_URI}" \
    --region "${REGION}" \
    --platform managed \
    --cpu 4 \
    --memory 8Gi \
    --timeout 1800 \
    --concurrency 80 \
    --min-instances 0 \
    --max-instances 1 \
    --no-cpu-throttling \
    --execution-environment gen2 \
    --port 8080 \
    --set-env-vars "MARKETING_MCP_DATA_DIR=/var/lib/marketing-mcp/data,MARKETING_MCP_INGEST_DIR=/var/lib/marketing-mcp/inbox,MARKETING_MCP_ARTIFACT_DIR=/var/lib/marketing-mcp/artifacts,MARKETING_MCP_METADATA_DB=/var/lib/marketing-mcp-local/metadata.db,MARKETING_MCP_TRANSPORT=streamable-http,MARKETING_MCP_API_KEY=${API_KEY},MARKETING_MCP_AUTH_ENABLED=true" \
    --add-volume "name=mcp-storage,type=cloud-storage,bucket=${BUCKET_NAME}" \
    --add-volume-mount "volume=mcp-storage,mount-path=/var/lib/marketing-mcp" \
    --allow-unauthenticated

SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')

echo "=========================================================="
echo " Deployment Completed Successfully with Active Auth!"
echo " Service Base URL:  ${SERVICE_URL}"
echo " MCP Endpoint:      ${SERVICE_URL}/mcp"
echo " Health Endpoint:   ${SERVICE_URL}/health"
echo " Active API Key:    ${API_KEY}"
echo "=========================================================="
echo ""
echo "Claude Desktop / Cursor / Antigravity Config Snippet:"
echo "----------------------------------------------------------"
cat << JSONEOF
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
JSONEOF
echo "----------------------------------------------------------"
echo ""
echo "Claude Code CLI Add Command:"
echo "  claude mcp add pymc-marketing ${SERVICE_URL}/mcp --header \"Authorization: Bearer ${API_KEY}\""
echo ""

