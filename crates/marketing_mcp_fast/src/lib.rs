//! High-performance Rust accelerator for pymc-marketing-mcp.
//!
//! Exposes PyO3 native functions for:
//! - MCP request admission and JSON-RPC framing validation
//! - HTTP Range header parsing
//! - Job admission tokens (interaction-level only, NOT canonical job IDs)
//! - Cancellation acknowledgment
//! - Dataset CSV preflight
//! - Quantile computation
//! - Sparkline generation
//! - LTTB curve downsampling (transport representation only)
//! - Native JSON serialization
//! - Native invocation counters for observability
//!
//! # Statistical authority
//! `fast_mcmc_diagnostics` and `fast_compute_split_rhat` are retained ONLY for
//! comparative benchmarks and parity testing. They must never be used for production
//! statistical decisions. Production authority resides exclusively in Python/ArviZ.

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

mod csv_preflight;
mod diagnostics;
mod engine;
mod quantiles;
mod sparklines;

use csv_preflight::sniff_and_validate_csv;
use diagnostics::{compute_split_rhat, evaluate_mcmc_gates};
use engine::{
    acknowledge_job_cancellation, admit_and_validate_request, admit_job_submission,
    get_native_stats, parse_range_header, DEFAULT_MAX_REQUEST_SIZE, NATIVE_SERIALIZATION_COUNT,
};
use quantiles::compute_quantiles;
use sparklines::{generate_sparkline as rust_generate_sparkline, lttb_downsample};
use std::sync::atomic::Ordering;

// ---------------------------------------------------------------------------
// MCP Request Admission
// ---------------------------------------------------------------------------

fn set_jsonrpc_id(
    py: Python,
    dict: &Bound<'_, PyDict>,
    key: &str,
    value: Option<&serde_json::Value>,
) -> PyResult<()> {
    match value {
        Some(serde_json::Value::String(value)) => dict.set_item(key, value),
        Some(serde_json::Value::Number(value)) => {
            if let Some(value) = value.as_i64() {
                dict.set_item(key, value)
            } else if let Some(value) = value.as_u64() {
                dict.set_item(key, value)
            } else if let Some(value) = value.as_f64() {
                dict.set_item(key, value)
            } else {
                Err(PyValueError::new_err("unsupported JSON-RPC numeric id"))
            }
        }
        Some(serde_json::Value::Null) | None => dict.set_item(key, py.None()),
        Some(_) => Err(PyValueError::new_err("invalid JSON-RPC id type")),
    }
}

#[pyfunction]
#[pyo3(signature = (raw_bytes, max_size=None, tenant_id=None))]
fn fast_admit_request(
    py: Python,
    raw_bytes: &[u8],
    max_size: Option<usize>,
    tenant_id: Option<String>,
) -> PyResult<PyObject> {
    let limit = max_size.unwrap_or(DEFAULT_MAX_REQUEST_SIZE);
    let dict = PyDict::new(py);
    match admit_and_validate_request(raw_bytes, limit, tenant_id.as_deref()) {
        Ok(admitted) => {
            dict.set_item("admitted", true)?;
            // request_id is None only for notifications; explicit JSON null is preserved.
            set_jsonrpc_id(py, &dict, "request_id", admitted.request_id.as_ref())?;
            dict.set_item("jsonrpc", admitted.jsonrpc)?;
            dict.set_item("method", admitted.method)?;
            match admitted.tool_name {
                Some(ref name) => dict.set_item("tool_name", name)?,
                None => dict.set_item("tool_name", py.None())?,
            }
            dict.set_item("payload_size", admitted.payload_size)?;
            dict.set_item("is_notification", admitted.is_notification)?;
            dict.set_item("error", py.None())?;
        }
        Err(err) => {
            dict.set_item("admitted", false)?;
            let err_dict = PyDict::new(py);
            err_dict.set_item("code", err.code)?;
            err_dict.set_item("category", err.category)?;
            err_dict.set_item("message", err.message)?;
            err_dict.set_item("error_id", err.error_id)?;
            set_jsonrpc_id(py, &err_dict, "request_id", err.request_id.as_ref())?;
            err_dict.set_item("is_notification", err.is_notification)?;
            match err.tenant_id {
                Some(ref tid) => err_dict.set_item("tenant_id", tid)?,
                None => err_dict.set_item("tenant_id", py.None())?,
            }
            err_dict.set_item("retryable", err.retryable)?;
            err_dict.set_item("actionable", err.actionable)?;
            dict.set_item("error", err_dict)?;
        }
    }
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// HTTP Range parsing
// ---------------------------------------------------------------------------

#[pyfunction]
fn fast_parse_range_header(header: &str, file_size: u64) -> Option<(u64, u64, u64)> {
    parse_range_header(header, file_size)
}

// ---------------------------------------------------------------------------
// Job Admission
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (payload_size, max_size=None, tenant_id=None))]
fn fast_admit_job(
    py: Python,
    payload_size: usize,
    max_size: Option<usize>,
    tenant_id: Option<String>,
) -> PyResult<PyObject> {
    let limit = max_size.unwrap_or(DEFAULT_MAX_REQUEST_SIZE);
    let dict = PyDict::new(py);
    match admit_job_submission(payload_size, limit, tenant_id.as_deref()) {
        Ok(adm) => {
            dict.set_item("admitted", true)?;
            // Expose as `admission_id` (NOT `job_id`) to prevent confusion with canonical job IDs
            dict.set_item("admission_id", adm.admission_id)?;
            dict.set_item("status", adm.status)?;
            dict.set_item("admitted_at", adm.admitted_at)?;
            dict.set_item(
                "recommended_poll_interval_ms",
                adm.recommended_poll_interval_ms,
            )?;
            dict.set_item("error", py.None())?;
        }
        Err(err) => {
            dict.set_item("admitted", false)?;
            let err_dict = PyDict::new(py);
            err_dict.set_item("code", err.code)?;
            err_dict.set_item("category", err.category)?;
            err_dict.set_item("message", err.message)?;
            err_dict.set_item("error_id", err.error_id)?;
            err_dict.set_item("retryable", err.retryable)?;
            err_dict.set_item("actionable", err.actionable)?;
            dict.set_item("error", err_dict)?;
        }
    }
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// Cancellation Acknowledgment
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (job_id, in_process=true))]
fn fast_acknowledge_cancellation(py: Python, job_id: &str, in_process: bool) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    match acknowledge_job_cancellation(job_id, in_process) {
        Ok(ack) => {
            dict.set_item("acknowledged", true)?;
            dict.set_item("job_id", ack.job_id)?;
            // Status reflects interaction-level state only; worker state is authoritative in Python
            dict.set_item("status", ack.status)?;
            dict.set_item("acknowledged_at", ack.acknowledged_at)?;
            dict.set_item("fence_triggered", ack.fence_triggered)?;
            dict.set_item("error", py.None())?;
        }
        Err(err) => {
            dict.set_item("acknowledged", false)?;
            let err_dict = PyDict::new(py);
            err_dict.set_item("code", err.code)?;
            err_dict.set_item("category", err.category)?;
            err_dict.set_item("message", err.message)?;
            err_dict.set_item("error_id", err.error_id)?;
            err_dict.set_item("retryable", err.retryable)?;
            err_dict.set_item("actionable", err.actionable)?;
            dict.set_item("error", err_dict)?;
        }
    }
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// Native Observability
// ---------------------------------------------------------------------------

/// Return a snapshot of native invocation counters for integration test verification.
#[pyfunction]
fn increment_native_fallback_count() {
    engine::NATIVE_FALLBACK_COUNT.fetch_add(1, Ordering::Relaxed);
}

#[pyfunction]
fn get_native_invocation_stats(py: Python) -> PyResult<PyObject> {
    let stats = get_native_stats();
    let dict = PyDict::new(py);
    dict.set_item("native_admission_calls_total", stats.admission_calls)?;
    dict.set_item(
        "native_serialization_calls_total",
        stats.serialization_calls,
    )?;
    dict.set_item("native_range_parse_calls_total", stats.range_parse_calls)?;
    dict.set_item(
        "native_job_admission_calls_total",
        stats.job_admission_calls,
    )?;
    dict.set_item("native_cancellation_calls_total", stats.cancellation_calls)?;
    dict.set_item("native_fallback_calls_total", stats.fallback_calls)?;
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

#[pyfunction]
fn get_version() -> &'static str {
    env!("CARGO_PKG_VERSION")
}

#[pyfunction]
fn is_rust_available() -> bool {
    true
}

// ---------------------------------------------------------------------------
// Sparkline and LTTB (transport-only downsampling)
// ---------------------------------------------------------------------------

#[pyfunction]
fn generate_sparkline(values: Vec<f64>) -> String {
    rust_generate_sparkline(&values)
}

#[pyfunction]
fn compress_curve_lttb(xs: Vec<f64>, ys: Vec<f64>, max_points: usize) -> (Vec<f64>, Vec<f64>) {
    lttb_downsample(&xs, &ys, max_points)
}

// ---------------------------------------------------------------------------
// Quantiles
// ---------------------------------------------------------------------------

#[pyfunction]
fn fast_compute_quantiles(py: Python, values: Vec<f64>, quantiles: Vec<f64>) -> PyResult<PyObject> {
    let summary = compute_quantiles(&values, &quantiles);
    let dict = PyDict::new(py);
    dict.set_item("mean", summary.mean)?;
    dict.set_item("std", summary.std)?;
    dict.set_item("min", summary.min)?;
    dict.set_item("max", summary.max)?;
    dict.set_item("count", summary.count)?;
    let q_list = PyList::new(py, summary.quantiles)?;
    dict.set_item("quantiles", q_list)?;
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// CSV Preflight
// ---------------------------------------------------------------------------

#[pyfunction]
#[pyo3(signature = (csv_bytes, date_col=None, target_col=None, channel_cols=None))]
fn fast_sniff_and_validate_csv(
    py: Python,
    csv_bytes: &[u8],
    date_col: Option<String>,
    target_col: Option<String>,
    channel_cols: Option<Vec<String>>,
) -> PyResult<PyObject> {
    let ch_refs: Option<Vec<&str>> = channel_cols
        .as_ref()
        .map(|v| v.iter().map(|s| s.as_str()).collect());
    let res = sniff_and_validate_csv(
        csv_bytes,
        date_col.as_deref(),
        target_col.as_deref(),
        ch_refs.as_deref(),
    )
    .map_err(pyo3::exceptions::PyValueError::new_err)?;

    let dict = PyDict::new(py);
    dict.set_item("row_count", res.row_count)?;
    dict.set_item("column_names", PyList::new(py, &res.column_names)?)?;
    dict.set_item("is_valid_for_modeling", res.is_valid_for_modeling)?;
    dict.set_item(
        "validation_errors",
        PyList::new(py, &res.validation_errors)?,
    )?;
    dict.set_item("date_min", res.date_min)?;
    dict.set_item("date_max", res.date_max)?;

    let cols_dict = PyDict::new(py);
    for (name, stats) in res.columns {
        let col_stat = PyDict::new(py);
        col_stat.set_item("name", stats.name)?;
        col_stat.set_item("detected_type", stats.detected_type)?;
        col_stat.set_item("null_count", stats.null_count)?;
        col_stat.set_item("min", stats.min)?;
        col_stat.set_item("max", stats.max)?;
        col_stat.set_item("mean", stats.mean)?;
        cols_dict.set_item(name, col_stat)?;
    }
    dict.set_item("columns", cols_dict)?;
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// Statistical diagnostics — EXPERIMENTAL ONLY
// NOTE: These functions are for benchmarking and parity testing ONLY.
// Production statistical decision authority resides exclusively in:
//   marketing_mcp.domain.diagnostics.engine.diagnose_inferencedata
// Never invoke these functions from production decision paths.
// ---------------------------------------------------------------------------

#[pyfunction]
fn fast_mcmc_diagnostics(
    py: Python,
    rhats: Vec<f64>,
    esses: Vec<f64>,
    divergences: usize,
) -> PyResult<PyObject> {
    let summary = evaluate_mcmc_gates(&rhats, &esses, divergences);
    let dict = PyDict::new(py);
    dict.set_item("max_rhat", summary.max_rhat)?;
    dict.set_item("min_ess", summary.min_ess)?;
    dict.set_item("divergences", summary.divergences)?;
    dict.set_item("decision_status", summary.decision_status)?;
    dict.set_item("decision_tools_enabled", summary.decision_tools_enabled)?;
    dict.set_item("failures", PyList::new(py, summary.failures)?)?;
    dict.set_item("warnings", PyList::new(py, summary.warnings)?)?;
    Ok(dict.into())
}

#[pyfunction]
fn fast_compute_split_rhat(chains: Vec<Vec<f64>>) -> f64 {
    compute_split_rhat(&chains)
}

// ---------------------------------------------------------------------------
// JSON Serialization
// ---------------------------------------------------------------------------

fn py_to_serde_value(obj: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if obj.is_none() {
        Ok(serde_json::Value::Null)
    } else if let Ok(b) = obj.extract::<bool>() {
        Ok(serde_json::Value::Bool(b))
    } else if let Ok(i) = obj.extract::<i64>() {
        Ok(serde_json::Value::Number(i.into()))
    } else if let Ok(f) = obj.extract::<f64>() {
        if f.is_nan() || f.is_infinite() {
            Ok(serde_json::Value::Null)
        } else if let Some(n) = serde_json::Number::from_f64(f) {
            Ok(serde_json::Value::Number(n))
        } else {
            Ok(serde_json::Value::Null)
        }
    } else if let Ok(s) = obj.extract::<String>() {
        Ok(serde_json::Value::String(s))
    } else if let Ok(dict) = obj.downcast::<pyo3::types::PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            let key_str = k.extract::<String>()?;
            let val = py_to_serde_value(&v)?;
            map.insert(key_str, val);
        }
        Ok(serde_json::Value::Object(map))
    } else if let Ok(list) = obj.downcast::<pyo3::types::PyList>() {
        let mut vec = Vec::with_capacity(list.len());
        for item in list.iter() {
            vec.push(py_to_serde_value(&item)?);
        }
        Ok(serde_json::Value::Array(vec))
    } else if let Ok(tuple) = obj.downcast::<pyo3::types::PyTuple>() {
        let mut vec = Vec::with_capacity(tuple.len());
        for item in tuple.iter() {
            vec.push(py_to_serde_value(&item)?);
        }
        Ok(serde_json::Value::Array(vec))
    } else {
        let s = obj.str()?.extract::<String>()?;
        Ok(serde_json::Value::String(s))
    }
}

#[pyfunction]
fn fast_serialize_json(obj: &Bound<'_, PyAny>) -> PyResult<String> {
    NATIVE_SERIALIZATION_COUNT.fetch_add(1, Ordering::Relaxed);
    let value = py_to_serde_value(obj)?;
    serde_json::to_string(&value)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn fast_serialize_json_bytes(obj: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    NATIVE_SERIALIZATION_COUNT.fetch_add(1, Ordering::Relaxed);
    let value = py_to_serde_value(obj)?;
    serde_json::to_vec(&value).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
#[pyo3(signature = (request_id=None, correlation_id=None, tool_name=None, arguments_json=None, tenant_id=None, deadline_ms=None, cancellation_token=None))]
fn fast_create_interaction_request(
    py: Python,
    request_id: Option<String>,
    correlation_id: Option<String>,
    tool_name: Option<String>,
    arguments_json: Option<String>,
    tenant_id: Option<String>,
    deadline_ms: Option<u64>,
    cancellation_token: Option<String>,
) -> PyResult<PyObject> {
    let req = engine::create_interaction_request(
        request_id,
        correlation_id,
        tool_name,
        arguments_json,
        tenant_id,
        deadline_ms,
        cancellation_token,
    );
    let dict = PyDict::new(py);
    dict.set_item("request_id", req.request_id)?;
    dict.set_item("correlation_id", req.correlation_id)?;
    dict.set_item("tool_name", req.tool_name)?;
    dict.set_item("arguments_json", req.arguments_json)?;
    dict.set_item("tenant_id", req.tenant_id)?;
    dict.set_item("deadline_ms", req.deadline_ms)?;
    dict.set_item("cancellation_token", req.cancellation_token)?;
    Ok(dict.into())
}

#[pyfunction]
#[pyo3(signature = (correlation_id=None, status="ok".to_string(), payload_json=None, execution_time_ms=0.0))]
fn fast_create_interaction_response(
    py: Python,
    correlation_id: Option<String>,
    status: String,
    payload_json: Option<String>,
    execution_time_ms: f64,
) -> PyResult<PyObject> {
    let resp = engine::create_interaction_response(
        correlation_id,
        status,
        payload_json,
        None,
        execution_time_ms,
    );
    let dict = PyDict::new(py);
    dict.set_item("correlation_id", resp.correlation_id)?;
    dict.set_item("status", resp.status)?;
    dict.set_item("payload_json", resp.payload_json)?;
    dict.set_item("error", py.None())?;
    dict.set_item("execution_time_ms", resp.execution_time_ms)?;
    Ok(dict.into())
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

#[pymodule]
fn marketing_mcp_fast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(get_version, m)?)?;
    m.add_function(wrap_pyfunction!(is_rust_available, m)?)?;
    m.add_function(wrap_pyfunction!(generate_sparkline, m)?)?;
    m.add_function(wrap_pyfunction!(compress_curve_lttb, m)?)?;
    m.add_function(wrap_pyfunction!(fast_compute_quantiles, m)?)?;
    m.add_function(wrap_pyfunction!(fast_sniff_and_validate_csv, m)?)?;
    m.add_function(wrap_pyfunction!(fast_serialize_json, m)?)?;
    m.add_function(wrap_pyfunction!(fast_serialize_json_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(fast_admit_request, m)?)?;
    m.add_function(wrap_pyfunction!(fast_parse_range_header, m)?)?;
    m.add_function(wrap_pyfunction!(fast_admit_job, m)?)?;
    m.add_function(wrap_pyfunction!(fast_acknowledge_cancellation, m)?)?;
    m.add_function(wrap_pyfunction!(get_native_invocation_stats, m)?)?;
    m.add_function(wrap_pyfunction!(increment_native_fallback_count, m)?)?;
    m.add_function(wrap_pyfunction!(fast_create_interaction_request, m)?)?;
    m.add_function(wrap_pyfunction!(fast_create_interaction_response, m)?)?;
    // Experimental / benchmark-only — see module docstring
    m.add_function(wrap_pyfunction!(fast_mcmc_diagnostics, m)?)?;
    m.add_function(wrap_pyfunction!(fast_compute_split_rhat, m)?)?;
    Ok(())
}
