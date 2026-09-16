//! High-performance MCP interaction engine: request admission, framing validation,
//! size enforcement, correlation tracking, and normalized error responses in native Rust.

#![allow(clippy::result_large_err)]

use serde::{Deserialize, Serialize};
use std::time::{SystemTime, UNIX_EPOCH};

pub const DEFAULT_MAX_REQUEST_SIZE: usize = 50 * 1024 * 1024; // 50 MB

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NormalizedEngineError {
    pub code: String,
    pub category: String,
    pub message: String,
    pub error_id: String,
    pub request_id: Option<String>,
    pub tenant_id: Option<String>,
    pub retryable: bool,
    pub actionable: bool,
}

impl NormalizedEngineError {
    pub fn new(
        code: &str,
        category: &str,
        message: &str,
        request_id: Option<String>,
        tenant_id: Option<String>,
        retryable: bool,
    ) -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_micros())
            .unwrap_or(0);
        let error_id = format!("err-{:x}", timestamp);

        Self {
            code: code.to_string(),
            category: category.to_string(),
            message: message.to_string(),
            error_id,
            request_id,
            tenant_id,
            retryable,
            actionable: true,
        }
    }

    #[allow(dead_code)]
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdmittedRequest {
    pub request_id: String,
    pub jsonrpc: String,
    pub method: String,
    pub tool_name: Option<String>,
    pub payload_size: usize,
    pub is_notification: bool,
}

/// Fast admission, size check, and framing inspection for raw inbound MCP requests.
pub fn admit_and_validate_request(
    bytes: &[u8],
    max_size: usize,
    tenant_id: Option<&str>,
) -> Result<AdmittedRequest, NormalizedEngineError> {
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
            tenant_id.map(|s| s.to_string()),
            false,
        ));
    }

    if bytes.is_empty() {
        return Err(NormalizedEngineError::new(
            "EMPTY_REQUEST",
            "protocol",
            "Request body is empty",
            None,
            tenant_id.map(|s| s.to_string()),
            false,
        ));
    }

    // 2. Fast JSON parsing and framing inspection
    let parsed: serde_json::Value = serde_json::from_slice(bytes).map_err(|e| {
        NormalizedEngineError::new(
            "MALFORMED_JSON_RPC",
            "protocol",
            &format!("Malformed JSON payload: {e}"),
            None,
            tenant_id.map(|s| s.to_string()),
            false,
        )
    })?;

    let obj = parsed.as_object().ok_or_else(|| {
        NormalizedEngineError::new(
            "INVALID_JSON_RPC",
            "protocol",
            "JSON-RPC payload must be a JSON object",
            None,
            tenant_id.map(|s| s.to_string()),
            false,
        )
    })?;

    // 3. Request ID extraction or generation
    let (request_id, is_notification) = if let Some(id_val) = obj.get("id") {
        let s = match id_val {
            serde_json::Value::String(s) => s.clone(),
            serde_json::Value::Number(n) => n.to_string(),
            _ => format!("{id_val}"),
        };
        (s, false)
    } else {
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_micros())
            .unwrap_or(0);
        (format!("req-{:x}", ts), true)
    };

    let method = obj
        .get("method")
        .and_then(|m| m.as_str())
        .unwrap_or("")
        .to_string();

    if method.is_empty() {
        return Err(NormalizedEngineError::new(
            "MISSING_METHOD",
            "protocol",
            "JSON-RPC request is missing required 'method' field",
            Some(request_id),
            tenant_id.map(|s| s.to_string()),
            false,
        ));
    }

    // Extract tool name if this is a tools/call request
    let tool_name = if method == "tools/call" {
        obj.get("params")
            .and_then(|p| p.get("name"))
            .and_then(|n| n.as_str())
            .map(|s| s.to_string())
    } else {
        None
    };

    let jsonrpc = obj
        .get("jsonrpc")
        .and_then(|v| v.as_str())
        .unwrap_or("2.0")
        .to_string();

    Ok(AdmittedRequest {
        request_id,
        jsonrpc,
        method,
        tool_name,
        payload_size: bytes.len(),
        is_notification,
    })
}

/// Parse HTTP Range header into `(start, end, chunk_length)`.
/// Returns `None` if header is not a valid satisfiable bytes range for `file_size`.
pub fn parse_range_header(header: &str, file_size: u64) -> Option<(u64, u64, u64)> {
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

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FastJobAdmission {
    pub job_id: String,
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
    if payload_size > max_size {
        return Err(NormalizedEngineError::new(
            "PAYLOAD_TOO_LARGE",
            "transport",
            &format!("Job submission payload ({payload_size} bytes) exceeds limit ({max_size} bytes)"),
            None,
            tenant_id.map(|s| s.to_string()),
            false,
        ));
    }
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_micros())
        .unwrap_or(0);
    let job_id = format!("job-{:x}", ts);
    let admitted_at = (ts / 1_000_000) as u64;

    Ok(FastJobAdmission {
        job_id,
        status: "accepted".to_string(),
        admitted_at,
        recommended_poll_interval_ms: 1000,
        is_valid: true,
    })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FastCancellationAck {
    pub job_id: String,
    pub status: String,
    pub acknowledged_at: u64,
    pub fence_triggered: bool,
}

pub fn acknowledge_job_cancellation(
    job_id: &str,
    in_process: bool,
) -> Result<FastCancellationAck, NormalizedEngineError> {
    let trimmed = job_id.trim();
    if trimmed.is_empty() {
        return Err(NormalizedEngineError::new(
            "INVALID_JOB_ID",
            "validation",
            "Job ID cannot be empty",
            None,
            None,
            false,
        ));
    }
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);

    Ok(FastCancellationAck {
        job_id: trimmed.to_string(),
        status: if in_process { "cancelled".to_string() } else { "cancelling".to_string() },
        acknowledged_at: ts,
        fence_triggered: true,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_range_header() {
        let size = 1000u64;
        assert_eq!(parse_range_header("bytes=0-499", size), Some((0, 499, 500)));
        assert_eq!(parse_range_header("bytes=500-", size), Some((500, 999, 500)));
        assert_eq!(parse_range_header("bytes=-100", size), Some((900, 999, 100)));
        assert_eq!(parse_range_header("bytes=1500-", size), None);
        assert_eq!(parse_range_header("invalid", size), None);
    }

    #[test]
    fn test_admit_valid_tool_call() {
        let raw = br#"{"jsonrpc":"2.0","id":"msg-42","method":"tools/call","params":{"name":"validate_dataset","arguments":{}}}"#;
        let admitted = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, Some("tenant-1")).unwrap();
        assert_eq!(admitted.request_id, "msg-42");
        assert_eq!(admitted.method, "tools/call");
        assert_eq!(admitted.tool_name.as_deref(), Some("validate_dataset"));
        assert!(!admitted.is_notification);
    }

    #[test]
    fn test_admit_payload_too_large() {
        let raw = vec![b'a'; 1024];
        let err = admit_and_validate_request(&raw, 512, None).unwrap_err();
        assert_eq!(err.code, "PAYLOAD_TOO_LARGE");
        assert_eq!(err.category, "transport");
        assert!(!err.retryable);
    }

    #[test]
    fn test_admit_malformed_json() {
        let raw = b"{\"jsonrpc\": \"2.0\", broken";
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "MALFORMED_JSON_RPC");
    }

    #[test]
    fn test_admit_missing_method() {
        let raw = b"{\"jsonrpc\": \"2.0\", \"id\": 1}";
        let err = admit_and_validate_request(raw, DEFAULT_MAX_REQUEST_SIZE, None).unwrap_err();
        assert_eq!(err.code, "MISSING_METHOD");
    }

    #[test]
    fn test_admit_job_submission_success_and_overflow() {
        let ok = admit_job_submission(1024, 10000, Some("t1")).unwrap();
        assert_eq!(ok.status, "accepted");
        assert!(ok.job_id.starts_with("job-"));

        let err = admit_job_submission(20000, 10000, Some("t1")).unwrap_err();
        assert_eq!(err.code, "PAYLOAD_TOO_LARGE");
    }

    #[test]
    fn test_acknowledge_job_cancellation() {
        let in_proc = acknowledge_job_cancellation("job-abc", true).unwrap();
        assert_eq!(in_proc.status, "cancelled");
        assert!(in_proc.fence_triggered);

        let async_proc = acknowledge_job_cancellation("job-abc", false).unwrap();
        assert_eq!(async_proc.status, "cancelling");

        let err = acknowledge_job_cancellation("", true).unwrap_err();
        assert_eq!(err.code, "INVALID_JOB_ID");
    }
}
