//! Fast empirical quantile, HDI, and statistical summary calculation using SIMD/Rayon.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantileSummary {
    pub mean: f64,
    pub std: f64,
    pub min: f64,
    pub max: f64,
    pub count: usize,
    pub quantiles: Vec<f64>,
}

/// Compute empirical quantiles matching NumPy's `np.quantile(method='linear')`.
pub fn compute_quantiles(values: &[f64], quantiles: &[f64]) -> QuantileSummary {
    let mut finite: Vec<f64> = values.iter().copied().filter(|v| v.is_finite()).collect();
    let count = finite.len();

    if count == 0 {
        return QuantileSummary {
            mean: f64::NAN,
            std: f64::NAN,
            min: f64::NAN,
            max: f64::NAN,
            count: 0,
            quantiles: vec![f64::NAN; quantiles.len()],
        };
    }

    finite.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let sum: f64 = finite.iter().sum();
    let mean = sum / (count as f64);

    let var: f64 = if count > 1 {
        finite.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / (count as f64)
    } else {
        0.0
    };
    let std = var.sqrt();

    let min = finite[0];
    let max = finite[count - 1];

    let computed_quantiles: Vec<f64> = quantiles
        .iter()
        .map(|&q| {
            if q <= 0.0 {
                return min;
            }
            if q >= 1.0 {
                return max;
            }
            let index = q * ((count - 1) as f64);
            let lower_idx = index.floor() as usize;
            let upper_idx = (lower_idx + 1).min(count - 1);
            let weight = index - (lower_idx as f64);
            finite[lower_idx] * (1.0 - weight) + finite[upper_idx] * weight
        })
        .collect();

    QuantileSummary {
        mean,
        std,
        min,
        max,
        count,
        quantiles: computed_quantiles,
    }
}
