# ---------------------------------------------------------
# Stage 1: Build native Rust acceleration extension
# ---------------------------------------------------------
FROM python:3.12-slim AS rust-builder

WORKDIR /build

# Install Rust toolchain and build tools in target Python 3.12 environment
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && echo "7d0ea0f8eba7fa1ebfe998091cd7ec4501e33ec5ca6b884eb4d894d7da5170af  /tmp/rustup-init.sh" | sha256sum -c - \
    && sh /tmp/rustup-init.sh -y --default-toolchain stable \
    && rm /tmp/rustup-init.sh \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

# Copy crate sources and Cargo manifests
COPY crates ./crates

# Build release extension
WORKDIR /build/crates/marketing_mcp_fast
RUN cargo build --release

# ---------------------------------------------------------
# Stage 2: Production Python runtime
# ---------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

# Install compilation tools needed by PyTensor C/C++ backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY dashboard/dist ./dashboard/dist

# Copy compiled Rust extension into python package directory
COPY --from=rust-builder /build/crates/marketing_mcp_fast/target/release/libmarketing_mcp_fast.so /app/src/marketing_mcp/accelerators/marketing_mcp_fast.so

# Deterministic frozen build matching CI locked dependencies
RUN pip install --no-cache-dir uv && \
    (uv export --format requirements-txt --no-hashes -o /tmp/requirements.txt 2>/dev/null && \
     uv pip install --system --no-cache -r /tmp/requirements.txt && \
     rm -f /tmp/requirements.txt) || \
    uv pip install --system --no-cache .

# Runtime activation verification: fail build if native extension is missing or unimportable
RUN python -c "from marketing_mcp.accelerators import is_rust_accelerated, get_engine_info; print('Native engine:', get_engine_info()); assert is_rust_accelerated(), 'Fatal: Rust acceleration extension not active in production image!'"



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

