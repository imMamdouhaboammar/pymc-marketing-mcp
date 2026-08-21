FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV MARKETING_MCP_DATA_DIR=/var/lib/marketing-mcp/data \
    MARKETING_MCP_INGEST_DIR=/var/lib/marketing-mcp/inbox \
    MARKETING_MCP_ARTIFACT_DIR=/var/lib/marketing-mcp/artifacts \
    MARKETING_MCP_METADATA_DB=/var/lib/marketing-mcp/metadata.db
RUN mkdir -p /var/lib/marketing-mcp/data /var/lib/marketing-mcp/artifacts /var/lib/marketing-mcp/inbox
EXPOSE 8000
CMD ["marketing-mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
