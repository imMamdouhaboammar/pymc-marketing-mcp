//! High-performance Rust accelerator for pymc-marketing-mcp.
//! Exposes PyO3 native functions for dataset preflight, quantiles, sparklines,
//! and MCMC decision gates.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

mod csv_preflight;
mod diagnostics;
mod engine;
mod quantiles;
mod sparklines;

use csv_preflight::sniff_and_validate_csv;
use diagnostics::{compute_split_rhat, evaluate_mcmc_gates};
use engine::{admit_and_validate_request, DEFAULT_MAX_REQUEST_SIZE};
use quantiles::compute_quantiles;
use sparklines::{generate_sparkline as rust_generate_sparkline, lttb_downsample};

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
            dict.set_item("request_id", admitted.request_id)?;
            dict.set_item("jsonrpc", admitted.jsonrpc)?;
            dict.set_item("method", admitted.method)?;
            dict.set_item("tool_name", admitted.tool_name)?;
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
            err_dict.set_item("request_id", err.request_id)?;
            err_dict.set_item("tenant_id", err.tenant_id)?;
            err_dict.set_item("retryable", err.retryable)?;
            err_dict.set_item("actionable", err.actionable)?;
            dict.set_item("error", err_dict)?;
        }
    }
    Ok(dict.into())
}

#[pyfunction]
fn fast_parse_range_header(header: &str, file_size: u64) -> Option<(u64, u64, u64)> {
    engine::parse_range_header(header, file_size)
}

#[pyfunction]
#[pyo3(signature = (payload_size, max_size=None, tenant_id=None))]
fn fast_admit_job(
    py: Python,
    payload_size: usize,
    max_size: Option<usize>,
    tenant_id: Option<String>,
) -> PyResult<PyObject> {
    let limit = max_size.unwrap_or(engine::DEFAULT_MAX_REQUEST_SIZE);
    let dict = PyDict::new(py);
    match engine::admit_job_submission(payload_size, limit, tenant_id.as_deref()) {
        Ok(adm) => {
            dict.set_item("admitted", true)?;
            dict.set_item("job_id", adm.job_id)?;
            dict.set_item("status", adm.status)?;
            dict.set_item("admitted_at", adm.admitted_at)?;
            dict.set_item("recommended_poll_interval_ms", adm.recommended_poll_interval_ms)?;
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
            dict.set_item("error", err_dict)?;
        }
    }
    Ok(dict.into())
}

#[pyfunction]
#[pyo3(signature = (job_id, in_process=true))]
fn fast_acknowledge_cancellation(
    py: Python,
    job_id: &str,
    in_process: bool,
) -> PyResult<PyObject> {
    let dict = PyDict::new(py);
    match engine::acknowledge_job_cancellation(job_id, in_process) {
        Ok(ack) => {
            dict.set_item("acknowledged", true)?;
            dict.set_item("job_id", ack.job_id)?;
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
            dict.set_item("error", err_dict)?;
        }
    }
    Ok(dict.into())
}

#[pyfunction]
fn get_version() -> &'static str {
    "0.1.0"
}

#[pyfunction]
fn is_rust_available() -> bool {
    true
}

#[pyfunction]
fn generate_sparkline(values: Vec<f64>) -> String {
    rust_generate_sparkline(&values)
}

#[pyfunction]
fn compress_curve_lttb(xs: Vec<f64>, ys: Vec<f64>, max_points: usize) -> (Vec<f64>, Vec<f64>) {
    lttb_downsample(&xs, &ys, max_points)
}

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

#[pyfunction]
#[pyo3(signature = (csv_bytes, date_col=None, target_col=None, channel_cols=None))]
fn fast_sniff_and_validate_csv(
    py: Python,
    csv_bytes: &[u8],
    date_col: Option<String>,
    target_col: Option<String>,
    channel_cols: Option<Vec<String>>,
) -> PyResult<PyObject> {
    let ch_refs: Option<Vec<&str>> = channel_cols.as_ref().map(|v| v.iter().map(|s| s.as_str()).collect());
    let res = sniff_and_validate_csv(
        csv_bytes,
        date_col.as_deref(),
        target_col.as_deref(),
        ch_refs.as_deref(),
    ).map_err(pyo3::exceptions::PyValueError::new_err)?;

    let dict = PyDict::new(py);
    dict.set_item("row_count", res.row_count)?;
    dict.set_item("column_names", PyList::new(py, &res.column_names)?)?;
    dict.set_item("is_valid_for_modeling", res.is_valid_for_modeling)?;
    dict.set_item("validation_errors", PyList::new(py, &res.validation_errors)?)?;
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
    let value = py_to_serde_value(obj)?;
    serde_json::to_string(&value).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pyfunction]
fn fast_serialize_json_bytes(obj: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    let value = py_to_serde_value(obj)?;
    serde_json::to_vec(&value).map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
}

#[pymodule]
fn marketing_mcp_fast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(get_version, m)?)?;
    m.add_function(wrap_pyfunction!(is_rust_available, m)?)?;
    m.add_function(wrap_pyfunction!(generate_sparkline, m)?)?;
    m.add_function(wrap_pyfunction!(compress_curve_lttb, m)?)?;
    m.add_function(wrap_pyfunction!(fast_compute_quantiles, m)?)?;
    m.add_function(wrap_pyfunction!(fast_sniff_and_validate_csv, m)?)?;
    m.add_function(wrap_pyfunction!(fast_mcmc_diagnostics, m)?)?;
    m.add_function(wrap_pyfunction!(fast_compute_split_rhat, m)?)?;
    m.add_function(wrap_pyfunction!(fast_serialize_json, m)?)?;
    m.add_function(wrap_pyfunction!(fast_serialize_json_bytes, m)?)?;
    m.add_function(wrap_pyfunction!(fast_admit_request, m)?)?;
    m.add_function(wrap_pyfunction!(fast_parse_range_header, m)?)?;
    m.add_function(wrap_pyfunction!(fast_admit_job, m)?)?;
    m.add_function(wrap_pyfunction!(fast_acknowledge_cancellation, m)?)?;
    Ok(())
}
