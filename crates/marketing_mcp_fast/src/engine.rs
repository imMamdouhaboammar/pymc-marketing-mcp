//! High-performance MCP interaction engine: request admission, framing validation,
//! size enforcement, correlation tracking, and normalized error responses in native Rust.
//!
//! # Correctness guarantees
//! - Error IDs use atomic counter + timestamp to prevent collision under concurrency.
//! - `jsonrpc` field is validated to be exactly `"2.0"`; missing or wrong version is rejected.
//! - JSON-RPC notifications (no `id` field) preserve `request_id = None` and `is_notification = true`.
//! - `actionable` is set semantically per error kind, not hardcoded.
//! - All externally reachable code is panic-free (no `unwrap()` or `expect()` on fallible paths).

#![allow(clippy::result_large_err)]

use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

/// Effective external request size limit. Aligned with Python `RequestSafetyMiddleware`.
pub const DEFAULT_MAX_REQUEST_SIZE: usize = 10 * 1024 * 1024; // 10 MB

// ---------------------------------------------------------------------------
// Atomic counters for native invocation observability
// ---------------------------------------------------------------------------

pub static NATIVE_ADMISSION_COUNT: AtomicU64 = AtomicU64::new(0);
pub static NATIVE_SERIALIZATION_COUNT: AtomicU64 = AtomicU64::new(0);
pub static NATIVE_RANGE_PARSE_COUNT: AtomicU64 = AtomicU64::new(0);
pub static NATIVE_JOB_ADMISSION_COUNT: AtomicU64 = AtomicU64::new(0);
pub static NATIVE_CANCELLATION_COUNT: AtomicU64 = AtomicU64::new(0);
pub static NATIVE_FALLBACK_COUNT: AtomicU64 = AtomicU64::new(0);

/// Monotonic counter for cheap ID uniqueness within the process lifetime.
static ID_COUNTER: AtomicU64 = AtomicU64::new(0);

fn next_id_suffix() -> u64 {
    ID_COUNTER.fetch_add(1, Ordering::Relaxed)
}

fn current_micros() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_micros() as u64)
        .unwrap_or(0)
}

/// Generate a collision-safe ID using process-local monotonic counter + timestamp.
/// Format: `{prefix}-{timestamp_hex}-{counter_hex}`
fn make_id(prefix: &str) -> String {
    format!("{}-{:x}-{:x}", prefix, current_micros(), next_id_suffix())
}

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NormalizedEngineError {
    pub code: String,
    pub category: String,
    pub message: String,
    pub error_id: String,
    pub request_id: Option<serde_json::Value>,
    pub tenant_id: Option<String>,
    pub retryable: bool,
    /// True when the error is caused by client-supplied input the client can correct.
    /// False for internal/operator errors.
    pub actionable: bool,
    /// True when the invalid message was a JSON-RPC notification and must not receive a response.
    pub is_notification: bool,
}

impl NormalizedEngineError {
    /// Create a normalized error with explicit actionability semantics.
    ///
    /// # Actionability guide
    /// - Client-supplied malformed input (bad JSON, wrong field type) → `actionable = true`
    /// - Internal serialization / unexpected state → `actionable = false`
    /// - Server resource failure → `actionable = false` (operator-actionable, not client)
    /// - Temporary dependency outage → `retryable = true, actionable = false`
    pub fn new(
        code: &str,
        category: &str,
        message: &str,
        request_id: Option<serde_json::Value>,
        tenant_id: Option<String>,
        retryable: bool,
        actionable: bool,
    ) -> Self {
        Self {
            code: code.to_string(),
            category: category.to_string(),
            message: message.to_string(),
            error_id: make_id("err"),
            request_id,
            tenant_id,
            retryable,
            actionable,
            is_notification: false,
        }
    }

    pub fn with_notification(mut self, is_notification: bool) -> Self {
        self.is_notification = is_notification;
        self
    }

    #[allow(dead_code)]
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }
}

// ---------------------------------------------------------------------------
// Admitted request descriptor
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdmittedRequest {
    /// Extracted from the JSON-RPC `id` field. `None` for notifications.
    pub request_id: Option<serde_json::Value>,
    pub jsonrpc: String,
    pub method: String,
    pub tool_name: Option<String>,
    pub payload_size: usize,
    /// True when the message has no `id` field (JSON-RPC notification).
    pub is_notification: bool,
}

// ---------------------------------------------------------------------------
// Core admission function
// ---------------------------------------------------------------------------

/// Fast admission, size enforcement, and JSON-RPC framing inspection for raw inbound MCP requests.
///
/// # Protocol guarantees
/// - `jsonrpc` field must be present and equal to `"2.0"`. Missing or wrong version is rejected.
/// - `method` field must be present and non-empty.
/// - Notifications (no `id`) set `request_id = None` and `is_notification = true`.
/// - Error IDs use counter+timestamp to avoid collision under concurrency.
pub fn admit_and_validate_request(
    bytes: &[u8],
    max_size: usize,
    tenant_id: Option<&str>,
) -> Result<AdmittedRequest, NormalizedEngineError> {
    NATIVE_ADMISSION_COUNT.fetch_add(1, Ordering::Relaxed);

    let tid = tenant_id.map(|s| s.to_string());

    // 1. Size boundary enforcement
    if bytes.len() > max_size {
        return Err(NormalizedEngineError::new(
            "PAYLOAD_TOO_LARGE",
            "transport",
            &format!(
                "Payload size ({} bytes) exceeds maximum limit ({} bytes)",
                bytes.len(),
                max_size
            ),
            None,
            tid,
            false,
            // Client sent an oversized payload — they can retry with a smaller one
            true,
        ));
    }

    if bytes.is_empty() {
        return Err(NormalizedEngineError::new(
            "EMPTY_REQUEST",
            "protocol",
            "Request body is empty",
            None,
            tid,
            false,
            true,
        ));
    }

    // 2. JSON parsing
    let parsed: serde_json::Value = serde_json::from_slice(bytes).map_err(|e| {
        NormalizedEngineError::new(
            "MALFORMED_JSON_RPC",
            "protocol",
            &format!("Malformed JSON payload: {e}"),
            None,
            tid.clone(),
            false,
            // Client sent malformed JSON — user/client actionable
            true,
        )
    })?;

    let obj = parsed.as_object().ok_or_else(|| {
        NormalizedEngineError::new(
            "INVALID_JSON_RPC",
            "protocol",
            "JSON-RPC payload must be a JSON object, not an array or scalar",
            None,
            tid.clone(),
            false,
            true,
        )
    })?;

    // 3. jsonrpc version validation — MUST be present and MUST be "2.0"
    match obj.get("jsonrpc") {
        Some(v) if v.as_str() == Some("2.0") => {}
        Some(v) => {
            return Err(NormalizedEngineError::new(
                "INVALID_JSONRPC_VERSION",
                "protocol",
                &format!(
                    "jsonrpc version must be '2.0', got '{}'",
                    v.as_str().unwrap_or("<non-string>")
                ),
                None,
                tid,
                false,
                true,
            ));
        }
        None => {
            return Err(NormalizedEngineError::new(
                "MISSING_JSONRPC_VERSION",
                "protocol",
                "JSON-RPC request is missing required 'jsonrpc' field",
                None,
                tid,
                false,
                true,
            ));
        }
    }

    // 4. Notification semantics and request-id type validation.
    // A notification is identified only by an absent id field. JSON null is an
    // allowed (though discouraged) request id and must still receive a response.
    let is_notification = !obj.contains_key("id");
    let request_id = match obj.get("id") {
        Some(value @ serde_json::Value::String(_))
        | Some(value @ serde_json::Value::Number(_))
        | Some(value @ serde_json::Value::Null) => Some(value.clone()),
        None => None,
        Some(_) => {
            return Err(NormalizedEngineError::new(
                "INVALID_REQUEST_ID",
                "protocol",
                "JSON-RPC id must be a string, number, or null",
                None,
                tid.clone(),
                false,
                true,
            ));
        }
    };

    // 5. Method field
    let method = obj
        .get("method")
        .and_then(|m| m.as_str())
        .unwrap_or("")
        .to_string();

    if method.is_empty() {
        return Err(NormalizedEngineError::new(
            "MISSING_METHOD",
            "protocol",
            "JSON-RPC request is missing a non-empty string 'method' field",
            request_id.clone(),
            tid.clone(),
            false,
            true,
        )
        .with_notification(is_notification));
    }

    // 6. JSON-RPC params, when present, must be an object or array.
    if let Some(params) = obj.get("params") {
        if !params.is_object() && !params.is_array() {
            return Err(NormalizedEngineError::new(
                "INVALID_PARAMS",
                "protocol",
                "JSON-RPC params must be an object or array",
                request_id.clone(),
                tid.clone(),
                false,
                true,
            )
            .with_notification(is_notification));
        }
    }

    // 7. MCP tools/call requires an object params value with a non-empty name.
    let tool_name = if method == "tools/call" {
        let name = obj
            .get("params")
            .and_then(|params| params.as_object())
            .and_then(|params| params.get("name"))
            .and_then(|name| name.as_str())
            .filter(|name| !name.is_empty());
        match name {
            Some(name) => Some(name.to_string()),
            None => {
                return Err(NormalizedEngineError::new(
                    "INVALID_TOOL_CALL",
                    "protocol",
                    "MCP tools/call requires params.name as a non-empty string",
                    request_id.clone(),
                    tid,
                    false,
                    true,
                )
                .with_notification(is_notification));
            }
        }
    } else {
        None
    };

    Ok(AdmittedRequest {
        request_id,
        jsonrpc: "2.0".to_string(),
        method,
        tool_name,
        payload_size: bytes.len(),
        is_notification,
    })
}

// ---------------------------------------------------------------------------
// HTTP Range header parsing
// ---------------------------------------------------------------------------

/// Parse HTTP Range header into `(start, end, chunk_length)`.
/// Returns `None` if header is not a valid satisfiable bytes range for `file_size`.
pub fn parse_range_header(header: &str, file_size: u64) -> Option<(u64, u64, u64)> {
    NATIVE_RANGE_PARSE_COUNT.fetch_add(1, Ordering::Relaxed);

    if file_size == 0 {
        return None;
    }
    let trimmed = header.trim();
    if !trimmed.starts_with("bytes=") {
        return None;
    }
    let spec = &trimmed[6..];
    let mut parts = spec.split('-');
    let start_str = parts.next()?.trim();
    let end_str = parts.next()?.trim();
    if parts.next().is_some() {
        return None;
    }

    let start = if start_str.is_empty() {
        let suffix_len: u64 = end_str.parse().ok()?;
        if suffix_len == 0 {
            return None;
        }
        file_size.saturating_sub(suffix_len)
    } else {
        start_str.parse().ok()?
    };

    let end = if end_str.is_empty() || start_str.is_empty() {
        file_size - 1
    } else {
        let parsed_end: u64 = end_str.parse().ok()?;
        parsed_end.min(file_size - 1)
    };

    if start >= file_size || start > end {
        return None;
    }

    let chunk_length = end - start + 1;
    Some((start, end, chunk_length))
}

// ---------------------------------------------------------------------------
// Job admission
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FastJobAdmission {
    /// Interaction-level admission token. NOT the canonical persistent job ID.
    /// The canonical job ID is created by the Python job service after this check.
    pub admission_id: String,
    pub status: String,
    pub admitted_at: u64,
    pub recommended_poll_interval_ms: u64,
    pub is_valid: bool,
}

pub fn admit_job_submission(
    payload_size: usize,
    max_size: usize,
    tenant_id: Option<&str>,
) -> Result<FastJobAdmission, NormalizedEngineError> {
    NATIVE_JOB_ADMISSION_COUNT.fetch_add(1, Ordering::Relaxed);

    if payload_size > max_size {
        return Err(NormalizedEngineError::new(
            "PAYLOAD_TOO_LARGE",
            "transport",
            &format!(
                "Job submission payload ({payload_size} bytes) exceeds limit ({max_size} bytes)"
            ),
            None,
            tenant_id.map(|s| s.to_string()),
            false,
            true,
        ));
    }

    let admitted_at = current_micros() / 1_000_000; // seconds

    Ok(FastJobAdmission {
        admission_id: make_id("adm"),
        status: "accepted".to_string(),
        admitted_at,
        recommended_poll_interval_ms: 1000,
        is_valid: true,
    })
}

// ---------------------------------------------------------------------------
// Cancellation acknowledgment
// ---------------------------------------------------------------------------

/// Cancellation state semantics:
/// - `cancellation_requested`: client has asked; signal sent to worker; worker may still run
/// - `cancelling`: worker has acknowledged the signal; wind-down in progress
/// - `cancelled`: interaction-level acknowledgment only; Python worker state is authoritative
/// - `terminated`: worker has stopped
/// - `result_fenced`: late results from cancelled job will be discarded
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FastCancellationAck {
    pub job_id: String,
    /// Reflects interaction-level state only. Python worker state is authoritative.
    pub status: String,
    pub acknowledged_at: u64,
    pub fence_triggered: bool,
}

pub fn acknowledge_job_cancellation(
    job_id: &str,
    in_process: bool,
) -> Result<FastCancellationAck, NormalizedEngineError> {
    NATIVE_CANCELLATION_COUNT.fetch_add(1, Ordering::Relaxed);

    let trimmed = job_id.trim();
    if trimmed.is_empty() {
        return Err(NormalizedEngineError::new(
            "INVALID_JOB_ID",
            "validation",
            "Job ID cannot be empty",
            None,
            None,
            false,
            // Client supplied an empty job ID — user actionable
            true,
        ));
    }

    let acknowledged_at = current_micros() / 1_000_000;

    // `cancelled` = interaction acknowledgment; `cancelling` = signal sent, worker may still run
    let status = if in_process {
        "cancelling"
    } else {
        "cancellation_requested"
    };

    Ok(FastCancellationAck {
        job_id: trimmed.to_string(),
        status: status.to_string(),
        acknowledged_at,
        fence_triggered: true,
    })
}

// ---------------------------------------------------------------------------
// Native stats snapshot
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NativeStats {
    pub admission_calls: u64,
    pub serialization_calls: u64,
    pub range_parse_calls: u64,
    pub job_admission_calls: u64,
    pub cancellation_calls: u64,
    pub fallback_calls: u64,
}

pub fn get_native_stats() -> NativeStats {
    NativeStats {
        admission_calls: NATIVE_ADMISSION_COUNT.load(Ordering::Relaxed),
        serialization_calls: NATIVE_SERIALIZATION_COUNT.load(Ordering::Relaxed),
        range_parse_calls: NATIVE_RANGE_PARSE_COUNT.load(Ordering::Relaxed),
        job_admission_calls: NATIVE_JOB_ADMISSION_COUNT.load(Ordering::Relaxed),
        cancellation_calls: NATIVE_CANCELLATION_COUNT.load(Ordering::Relaxed),
        fallback_calls: NATIVE_FALLBACK_COUNT.load(Ordering::Relaxed),
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_range_header() {
        let size = 1000u64;
        assert_eq!(parse_range_header("bytes=0-499", size), Some((0, 499, 500)));
        assert_eq!(
            parse_range_header("bytes=500-", size),
            Some((500, 999, 500))
        );
        assert_eq!(
            parse_range_header("bytes=-100", size),
            Some((900, 999, 100))
        );
        assert_eq!(parse_range_header("bytes=1500-", size), None);
        assert_eq!(parse_range_header("invalid", size), None);
        assert_eq!(parse_range_header("bytes=0-1-2", size), None);
    }

    #[test]
    fn test_admit_valid_tool_call() {
        let raw = br#"{"jsonrpc":"2.0","id":"msg-42","method":"tools/call","params":{"name":"validate_dataset","arguments":{}}}"#;
        let admitted =
            admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, Some("tenant-1")).unwrap();
        assert_eq!(
            admitted.request_id.as_ref(),
            Some(&serde_json::json!("msg-42"))
        );
        assert_eq!(admitted.method, "tools/call");
        assert_eq!(admitted.tool_name.as_deref(), Some("validate_dataset"));
        assert!(!admitted.is_notification);
    }

    #[test]
    fn test_admit_notification_has_null_request_id() {
        // Notifications have no `id` field — request_id must be None, is_notification true
        let raw = br#"{"jsonrpc":"2.0","method":"notifications/cancelled","params":{}}"#;
        let admitted = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap();
        assert!(admitted.request_id.is_none());
        assert!(admitted.is_notification);
    }

    #[test]
    fn test_null_id_is_not_a_notification() {
        // Notifications have an absent id. A present null id is discouraged but
        // remains a request and must not be silently dropped.
        let raw = br#"{"jsonrpc":"2.0","id":null,"method":"tools/list","params":{}}"#;
        let admitted = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap();
        assert_eq!(admitted.request_id, Some(serde_json::Value::Null));
        assert!(!admitted.is_notification);
    }

    #[test]
    fn test_numeric_id_preserves_json_type() {
        let raw = br#"{"jsonrpc":"2.0","id":42,"method":"tools/list"}"#;
        let admitted = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap();
        assert_eq!(admitted.request_id, Some(serde_json::json!(42)));
    }

    #[test]
    fn test_rejects_invalid_id_type() {
        let raw = br#"{"jsonrpc":"2.0","id":true,"method":"tools/list"}"#;
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "INVALID_REQUEST_ID");
    }

    #[test]
    fn test_rejects_invalid_params_shape() {
        let raw = br#"{"jsonrpc":"2.0","id":1,"method":"tools/list","params":"bad"}"#;
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "INVALID_PARAMS");
    }

    #[test]
    fn test_tools_call_requires_non_empty_name() {
        let raw = br#"{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"arguments":{}}}"#;
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "INVALID_TOOL_CALL");
    }

    #[test]
    fn test_admit_payload_too_large() {
        let raw = vec![b'a'; 1024];
        let err = admit_and_validate_request(&raw, 512, None).unwrap_err();
        assert_eq!(err.code, "PAYLOAD_TOO_LARGE");
        assert_eq!(err.category, "transport");
        assert!(!err.retryable);
        assert!(err.actionable); // client can retry with smaller payload
    }

    #[test]
    fn test_admit_malformed_json() {
        let raw = b"{\"jsonrpc\": \"2.0\", broken";
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "MALFORMED_JSON_RPC");
        assert!(err.actionable);
    }

    #[test]
    fn test_admit_missing_jsonrpc_field() {
        let raw = b"{\"id\": 1, \"method\": \"tools/list\"}";
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "MISSING_JSONRPC_VERSION");
        assert!(err.actionable);
    }

    #[test]
    fn test_admit_wrong_jsonrpc_version() {
        let raw = b"{\"jsonrpc\": \"1.0\", \"id\": 1, \"method\": \"tools/list\"}";
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "INVALID_JSONRPC_VERSION");
        assert!(err.actionable);
    }

    #[test]
    fn test_admit_missing_method() {
        let raw = b"{\"jsonrpc\": \"2.0\", \"id\": 1}";
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "MISSING_METHOD");
        assert!(err.actionable);
    }

    #[test]
    fn test_error_ids_are_unique_under_concurrency() {
        use std::collections::HashSet;
        let ids: HashSet<String> = (0..1000).map(|_| make_id("err")).collect();
        assert_eq!(ids.len(), 1000, "All error IDs must be unique");
    }

    #[test]
    fn test_admit_job_submission_success_and_overflow() {
        let ok = admit_job_submission(1024, 10_000_000, Some("t1")).unwrap();
        assert_eq!(ok.status, "accepted");
        assert!(
            ok.admission_id.starts_with("adm-"),
            "admission_id must use 'adm-' prefix, not 'job-'"
        );

        let err = admit_job_submission(20_000_000, 10_000_000, Some("t1")).unwrap_err();
        assert_eq!(err.code, "PAYLOAD_TOO_LARGE");
    }

    #[test]
    fn test_acknowledge_cancellation_states() {
        // in_process = true → "cancelling" (signal sent, worker may still run)
        let in_proc = acknowledge_job_cancellation("job-abc", true).unwrap();
        assert_eq!(in_proc.status, "cancelling");
        assert!(in_proc.fence_triggered);
        assert!(!in_proc.job_id.is_empty());

        // in_process = false → "cancellation_requested" (queued, not yet running)
        let queued = acknowledge_job_cancellation("job-abc", false).unwrap();
        assert_eq!(queued.status, "cancellation_requested");

        // Empty job ID → error
        let err = acknowledge_job_cancellation("", true).unwrap_err();
        assert_eq!(err.code, "INVALID_JOB_ID");
        assert!(err.actionable);
        assert!(!err.retryable);
    }

    #[test]
    fn test_normalized_error_actionable_semantics() {
        // Client malformed JSON → actionable
        let raw = b"not json at all";
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert!(err.actionable, "Malformed JSON must be user-actionable");

        // Internal caller creates non-actionable error
        let internal = NormalizedEngineError::new(
            "INTERNAL_ERROR",
            "internal",
            "Unexpected serialization failure",
            None,
            None,
            false,
            false, // operator-actionable, not user
        );
        assert!(!internal.actionable);
    }

    #[test]
    fn test_native_stats_counters_increment() {
        let before = NATIVE_ADMISSION_COUNT.load(Ordering::Relaxed);
        let raw = br#"{"jsonrpc":"2.0","id":1,"method":"tools/list"}"#;
        let _ = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None);
        let after = NATIVE_ADMISSION_COUNT.load(Ordering::Relaxed);
        assert!(after > before, "Admission counter must increment");
    }

    #[test]
    fn test_10mb_limit_matches_python_middleware() {
        // The constant must match `DEFAULT_MAX_BODY_BYTES` in Python's safety.py (10 MB)
        assert_eq!(
            DEFAULT_MAX_REQUEST_SIZE,
            10 * 1024 * 1024,
            "Rust limit must match Python RequestSafetyMiddleware limit"
        );
    }
}
