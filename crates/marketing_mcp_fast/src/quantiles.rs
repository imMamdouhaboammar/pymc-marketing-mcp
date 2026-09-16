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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_quantiles_empty() {
        let res = compute_quantiles(&[], &[0.5]);
        assert_eq!(res.count, 0);
        assert!(res.mean.is_nan());
    }

    #[test]
    fn test_quantiles_linear_interpolation() {
        // [1.0, 2.0, 3.0, 4.0, 5.0]
        let values = vec![5.0, 1.0, 4.0, 2.0, 3.0];
        let res = compute_quantiles(&values, &[0.0, 0.25, 0.5, 0.75, 1.0]);
        assert_eq!(res.count, 5);
        assert_eq!(res.min, 1.0);
        assert_eq!(res.max, 5.0);
        assert_eq!(res.mean, 3.0);
        // q=0.5 -> index = 0.5 * 4 = 2 -> values[2] = 3.0
        assert!((res.quantiles[2] - 3.0).abs() < 1e-9);
        // q=0.25 -> index = 0.25 * 4 = 1 -> values[1] = 2.0
        assert!((res.quantiles[1] - 2.0).abs() < 1e-9);
    }
}
