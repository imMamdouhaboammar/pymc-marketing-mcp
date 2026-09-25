#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# PyMC Marketing MCP - Google Cloud Run deployment (single instance)
#
#   scripts/deploy_cloud_run.sh            # API-key protected (default)
#   scripts/deploy_cloud_run.sh --beta     # anonymous, for throwaway demos only
#
# Topology: one Cloud Run instance, SQLite on instance disk snapshotted into a GCS
# bucket mounted at /var/lib/marketing-mcp, secrets from Secret Manager.
# max-instances stays at 1: the SQLite snapshot supports exactly one writer.
# ==============================================================================

if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

MODE="secure"
case "${1:-}" in
    --beta|beta) MODE="beta" ;;
    ""|--secure|secure) MODE="secure" ;;
    *) echo "usage: $0 [--secure|--beta]" >&2; exit 64 ;;
esac

if ! command -v gcloud >/dev/null 2>&1; then
    echo "ERROR: gcloud CLI is required (https://cloud.google.com/sdk/docs/install)" >&2
    exit 1
fi

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo '')}"
if [ -z "${PROJECT_ID}" ]; then
    echo "ERROR: set GCP_PROJECT_ID or run 'gcloud config set project <PROJECT_ID>'" >&2
    exit 1
fi
# Every gcloud call below targets this project, whatever the active gcloud config says.
export CLOUDSDK_CORE_PROJECT="${PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${GCP_SERVICE_NAME:-pymc-marketing-mcp}"
REPO_NAME="${GCP_REPO_NAME:-mcp-servers}"
BUCKET_NAME="${GCS_BUCKET_NAME:-${PROJECT_ID}-pymc-mcp-artifacts}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"
APP_VERSION="${APP_VERSION:-$(python3 -c 'import marketing_mcp; print(marketing_mcp.__version__)' 2>/dev/null || echo 'unknown')}"
GIT_SHA="${GIT_SHA:-$(git rev-parse --short=12 HEAD 2>/dev/null || echo 'unknown')}"
IMAGE_TAG="${IMAGE_TAG:-${APP_VERSION}-g${GIT_SHA}}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}:${IMAGE_TAG}"
API_KEY_SECRET="${SERVICE_NAME}-api-key"
TOKEN_SECRET="${SERVICE_NAME}-token-secret"

echo "Project ${PROJECT_ID} | region ${REGION} | service ${SERVICE_NAME} | mode ${MODE}"
echo "Image   ${IMAGE_URI}"
echo "Bucket  gs://${BUCKET_NAME}"

gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    cloudbuild.googleapis.com storage.googleapis.com secretmanager.googleapis.com >/dev/null

if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" >/dev/null 2>&1; then
    gcloud artifacts repositories create "${REPO_NAME}" --repository-format=docker \
        --location="${REGION}" --description="PyMC Marketing MCP images" >/dev/null
fi

if ! gcloud storage buckets describe "gs://${BUCKET_NAME}" >/dev/null 2>&1; then
    gcloud storage buckets create "gs://${BUCKET_NAME}" --location="${REGION}" \
        --uniform-bucket-level-access >/dev/null
fi
# Object versioning keeps earlier metadata snapshots recoverable after a bad write.
gcloud storage buckets update "gs://${BUCKET_NAME}" --versioning >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "${PROJECT_ID}" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Create a secret with a random value once; later deploys reuse it.
ensure_secret() {
    local name="$1"
    if ! gcloud secrets describe "${name}" >/dev/null 2>&1; then
        python3 -c 'import secrets; print("mcp_" + secrets.token_hex(32), end="")' |
            gcloud secrets create "${name}" --replication-policy=automatic --data-file=- >/dev/null
        echo "Created secret ${name}"
    fi
    gcloud secrets add-iam-policy-binding "${name}" \
        --member="serviceAccount:${RUNTIME_SA}" \
        --role=roles/secretmanager.secretAccessor >/dev/null
}

ensure_secret "${TOKEN_SECRET}"
SECRETS="MARKETING_MCP_TOKEN_SECRET=${TOKEN_SECRET}:latest"
if [ "${MODE}" = "secure" ]; then
    ensure_secret "${API_KEY_SECRET}"
    SECRETS="${SECRETS},MARKETING_MCP_API_KEY=${API_KEY_SECRET}:latest"
    AUTH_ENV="MARKETING_MCP_SECURITY_PROFILE=http-private-api-key"
else
    echo "WARNING: --beta serves every tool and every stored dataset to anyone with the URL." >&2
    AUTH_ENV="MARKETING_MCP_ALLOW_ANONYMOUS_HTTP=true"
fi

BUILD_CONFIG="$(mktemp)"
trap 'rm -f "${BUILD_CONFIG}"' EXIT
cat > "${BUILD_CONFIG}" <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: [build, --build-arg, APP_VERSION=${APP_VERSION}, --build-arg, GIT_COMMIT=${GIT_SHA}, -t, ${IMAGE_URI}, .]
images: [${IMAGE_URI}]
EOF
gcloud builds submit --quiet --config="${BUILD_CONFIG}" .

gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_URI}" \
    --region "${REGION}" \
    --cpu 4 \
    --memory 8Gi \
    --timeout 1800 \
    --concurrency 80 \
    --min-instances "${MIN_INSTANCES}" \
    --max-instances 1 \
    --no-cpu-throttling \
    --execution-environment gen2 \
    --port 8080 \
    --set-env-vars "${AUTH_ENV},MARKETING_MCP_MAX_ARTIFACT_SIZE_MB=2048" \
    --set-secrets "${SECRETS}" \
    --add-volume "name=mcp-storage,type=cloud-storage,bucket=${BUCKET_NAME},mount-options=uid=10001;gid=10001" \
    --add-volume-mount "volume=mcp-storage,mount-path=/var/lib/marketing-mcp" \
    --allow-unauthenticated \
    --quiet

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format='value(status.url)')"
# Artifact export links are built from this base URL.
gcloud run services update "${SERVICE_NAME}" --region="${REGION}" \
    --update-env-vars "MARKETING_MCP_PUBLIC_BASE_URL=${SERVICE_URL}" --quiet >/dev/null

echo ""
echo "Deployed ${SERVICE_URL}"
echo "  MCP endpoint: ${SERVICE_URL}/mcp"
echo "  Readiness:    ${SERVICE_URL}/health/ready"
if [ "${MODE}" = "secure" ]; then
    echo ""
    echo "Read the API key (never commit it):"
    echo "  gcloud secrets versions access latest --secret=${API_KEY_SECRET}"
    echo "Connect Claude Code:"
    echo "  claude mcp add --transport http pymc-marketing ${SERVICE_URL}/mcp --header \"Authorization: Bearer <API_KEY>\""
fi
