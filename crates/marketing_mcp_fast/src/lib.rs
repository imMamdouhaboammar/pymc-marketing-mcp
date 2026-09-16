//! High-performance Rust accelerator for pymc-marketing-mcp.
//! Exposes PyO3 native functions for dataset preflight, quantiles, sparklines,
//! and MCMC decision gates.

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

mod csv_preflight;
mod diagnostics;
mod quantiles;
mod sparklines;

use csv_preflight::sniff_and_validate_csv;
use diagnostics::{compute_split_rhat, evaluate_mcmc_gates};
use quantiles::compute_quantiles;
use sparklines::{generate_sparkline as rust_generate_sparkline, lttb_downsample};

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
    ).map_err(|e| pyo3::exceptions::PyValueError::new_err(e))?;

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

#[pyfunction]
fn fast_serialize_json(py: Python, obj: PyObject) -> PyResult<String> {
    // Uses serde_json for fast string dump via python's json module or pyo3
    let json_module = py.import("json")?;
    let res = json_module.call_method1("dumps", (obj,))?;
    res.extract::<String>()
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
    Ok(())
}
