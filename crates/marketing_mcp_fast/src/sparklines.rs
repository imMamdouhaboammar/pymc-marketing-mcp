//! Sparkline and curve downsampling implementations for AI client context efficiency.

/// Generate a compact unicode sparkline string from a series of floating-point values.
/// Block characters:  ▂▃▄▅▆▇█
pub fn generate_sparkline(values: &[f64]) -> String {
    if values.is_empty() {
        return String::new();
    }

    let finite_values: Vec<f64> = values.iter().copied().filter(|v| v.is_finite()).collect();
    if finite_values.is_empty() {
        return " ".repeat(values.len());
    }

    let mut min_val = f64::INFINITY;
    let mut max_val = f64::NEG_INFINITY;
    for &v in &finite_values {
        if v < min_val {
            min_val = v;
        }
        if v > max_val {
            max_val = v;
        }
    }

    let blocks = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█'];
    let range = max_val - min_val;

    values
        .iter()
        .map(|&v| {
            if !v.is_finite() {
                ' '
            } else if range <= 1e-12 {
                '▄'
            } else {
                let norm = ((v - min_val) / range).clamp(0.0, 1.0);
                let idx = ((norm * 7.0).round() as usize).min(7);
                blocks[idx]
            }
        })
        .collect()
}

/// Largest-Triangle-Three-Buckets (LTTB) algorithm for downsampling 2D curves to `threshold` points.
pub fn lttb_downsample(xs: &[f64], ys: &[f64], threshold: usize) -> (Vec<f64>, Vec<f64>) {
    let n = xs.len();
    if n <= threshold || threshold < 3 || n != ys.len() {
        return (xs.to_vec(), ys.to_vec());
    }

    let mut sampled_x = Vec::with_capacity(threshold);
    let mut sampled_y = Vec::with_capacity(threshold);

    // Bucket size. Leave room for start and end data points.
    let every = (n - 2) as f64 / (threshold - 2) as f64;

    // First point is always included
    sampled_x.push(xs[0]);
    sampled_y.push(ys[0]);

    let mut a_idx = 0;

    for i in 0..(threshold - 2) {
        // Calculate point average for next bucket (bucket c)
        let c_start = (((i + 1) as f64 * every) as usize + 1).min(n - 1);
        let c_end = (((i + 2) as f64 * every) as usize + 1).min(n);
        let c_len = (c_end - c_start) as f64;

        let mut avg_x = 0.0;
        let mut avg_y = 0.0;
        if c_len > 0.0 {
            for j in c_start..c_end {
                avg_x += xs[j];
                avg_y += ys[j];
            }
            avg_x /= c_len;
            avg_y /= c_len;
        } else {
            avg_x = xs[c_start];
            avg_y = ys[c_start];
        }

        // Get the range for current bucket (bucket b)
        let b_start = ((i as f64 * every) as usize + 1).min(n - 1);
        let b_end = (((i + 1) as f64 * every) as usize + 1).min(n);

        // Point a
        let ax = xs[a_idx];
        let ay = ys[a_idx];

        let mut max_area = -1.0;
        let mut next_a_idx = b_start;

        for j in b_start..b_end {
            // Triangle area: 0.5 * |(ax - avg_x)(y_j - ay) - (ax - x_j)(avg_y - ay)|
            let area = ((ax - avg_x) * (ys[j] - ay) - (ax - xs[j]) * (avg_y - ay)).abs() * 0.5;
            if area > max_area {
                max_area = area;
                next_a_idx = j;
            }
        }

        sampled_x.push(xs[next_a_idx]);
        sampled_y.push(ys[next_a_idx]);
        a_idx = next_a_idx;
    }

    // Always include the last point
    sampled_x.push(xs[n - 1]);
    sampled_y.push(ys[n - 1]);

    (sampled_x, sampled_y)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sparkline_basic() {
        let values = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0];
        let spark = generate_sparkline(&values);
        assert_eq!(spark.chars().count(), 8);
        assert_eq!(spark.chars().next().unwrap(), ' ');
        assert_eq!(spark.chars().last().unwrap(), '█');
    }

    #[test]
    fn test_sparkline_empty_and_constant() {
        assert_eq!(generate_sparkline(&[]), "");
        assert_eq!(generate_sparkline(&[5.0, 5.0, 5.0]), "▄▄▄");
    }

    #[test]
    fn test_sparkline_nan_handling() {
        let values = vec![1.0, f64::NAN, 10.0];
        let spark = generate_sparkline(&values);
        assert_eq!(spark.chars().count(), 3);
        let chars: Vec<char> = spark.chars().collect();
        assert_eq!(chars[0], ' ');
        assert_eq!(chars[1], ' ');
        assert_eq!(chars[2], '█');
    }

    #[test]
    fn test_lttb_downsample_preserves_endpoints() {
        let xs: Vec<f64> = (0..100).map(|i| i as f64).collect();
        let ys: Vec<f64> = xs.iter().map(|&x| x.sin()).collect();
        let (down_x, down_y) = lttb_downsample(&xs, &ys, 10);
        assert_eq!(down_x.len(), 10);
        assert_eq!(down_y.len(), 10);
        assert_eq!(down_x[0], 0.0);
        assert_eq!(down_x[9], 99.0);
    }

    #[test]
    fn test_lttb_under_threshold() {
        let xs = vec![1.0, 2.0];
        let ys = vec![10.0, 20.0];
        let (down_x, down_y) = lttb_downsample(&xs, &ys, 5);
        assert_eq!(down_x, xs);
        assert_eq!(down_y, ys);
    }
}
