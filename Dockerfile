FROM python:3.12-slim

WORKDIR /app

# Install compilation tools needed by PyTensor C/C++ backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY dashboard/dist ./dashboard/dist

RUN pip install --no-cache-dir .


ENV MARKETING_MCP_DATA_DIR=/var/lib/marketing-mcp/data \
    MARKETING_MCP_INGEST_DIR=/var/lib/marketing-mcp/inbox \
    MARKETING_MCP_ARTIFACT_DIR=/var/lib/marketing-mcp/artifacts \
    MARKETING_MCP_METADATA_DB=/var/lib/marketing-mcp-local/metadata.db \
    MARKETING_MCP_TRANSPORT=streamable-http \
    PORT=8080 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /var/lib/marketing-mcp-local /var/lib/marketing-mcp/data /var/lib/marketing-mcp/artifacts /var/lib/marketing-mcp/inbox


# Release identity, supplied by the build pipeline (deploy_cloud_run.sh / cloudbuild.yaml).
# Declared late so a version/commit change does not invalidate the dependency layers above.
ARG APP_VERSION=0.0.0
ARG GIT_COMMIT=unknown
LABEL org.opencontainers.image.title="pymc-marketing-mcp" \
      org.opencontainers.image.description="Decision-safe MCP server for Bayesian marketing science" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.source="https://github.com/imMamdouhaboammar/pymc-marketing-mcp" \
      org.opencontainers.image.licenses="Apache-2.0"

EXPOSE 8080 8000

CMD ["marketing-mcp", "--transport", "streamable-http"]

