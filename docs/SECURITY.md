# Security

Threat boundary: an MCP client is untrusted input. V1 rejects arbitrary code execution, shell, SQL, pickle/joblib deserialization and caller-selected artifact paths. Dataset ingestion is limited to CSV/Parquet and an explicit size ceiling. Stable generated IDs prevent path traversal. Raw rows are not returned by MCP tools. Logs should record IDs and timings, not source datasets.

For remote Streamable HTTP deployments, configure the SDK's transport security/host allowlist and put authentication in front of the endpoint. The current SDK enables DNS-rebinding protection for local defaults; production host/origin settings must be explicit.
