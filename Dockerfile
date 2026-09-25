# ---------------------------------------------------------
# Stage 1: Build native Rust acceleration extension
# ---------------------------------------------------------
FROM python:3.12-slim AS rust-builder

WORKDIR /build

# Take the Rust toolchain from the official image rather than piping a remote installer
# into sh, where a failed download would not fail the build.
COPY --from=rust:1-slim /usr/local/rustup /usr/local/rustup
COPY --from=rust:1-slim /usr/local/cargo /usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:${PATH}"

# Debian rotates patch versions out of the archive, so apt pins would break rebuilds.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && cargo --version

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

# PyTensor compiles C/C++ at runtime, so the compiler toolchain stays in the image.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY dashboard/dist ./dashboard/dist

# Copy compiled Rust extension into python package directory
COPY --from=rust-builder /build/crates/marketing_mcp_fast/target/release/libmarketing_mcp_fast.so /app/src/marketing_mcp/accelerators/marketing_mcp_fast.so

# Install exactly the locked dependency set; a lock mismatch fails the build instead of
# silently resolving fresh versions. The project is installed editable so the native
# extension copied into /app/src is the one that gets imported.
RUN pip install --no-cache-dir uv==0.8.17 && \
    uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt && \
    uv pip install --system --no-cache --no-deps -e . && \
    rm -f /tmp/requirements.txt

# Runtime activation verification: fail build if native extension is missing or unimportable
RUN python -c "from marketing_mcp.accelerators import is_rust_accelerated, get_engine_info; print('Native engine:', get_engine_info()); assert is_rust_accelerated(), 'Fatal: Rust acceleration extension not active in production image!'"

# Durable data lives on /var/lib/marketing-mcp (mount a volume or bucket there). SQLite
# stays on local disk and is snapshotted onto the durable path.
ENV MARKETING_MCP_DATA_DIR=/var/lib/marketing-mcp/data \
    MARKETING_MCP_INGEST_DIR=/var/lib/marketing-mcp/inbox \
    MARKETING_MCP_ARTIFACT_DIR=/var/lib/marketing-mcp/artifacts \
    MARKETING_MCP_METADATA_DB=/var/lib/marketing-mcp-local/metadata.db \
    MARKETING_MCP_METADATA_SNAPSHOT=/var/lib/marketing-mcp/state/metadata.db \
    MARKETING_MCP_TRANSPORT=streamable-http \
    PORT=8080 \
    HOST=0.0.0.0 \
    HOME=/home/app \
    PYTHONUNBUFFERED=1

RUN useradd --uid 10001 --create-home --home-dir /home/app --shell /usr/sbin/nologin app && \
    mkdir -p /var/lib/marketing-mcp-local /var/lib/marketing-mcp/data /var/lib/marketing-mcp/artifacts \
             /var/lib/marketing-mcp/inbox /var/lib/marketing-mcp/state && \
    chown -R app:app /var/lib/marketing-mcp-local /var/lib/marketing-mcp

USER 10001:10001

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

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8080') + '/health/live', timeout=4)"]

CMD ["marketing-mcp", "--transport", "streamable-http"]

