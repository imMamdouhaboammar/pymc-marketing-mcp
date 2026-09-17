//! Fast SIMD CSV preflight inspection and validation engine.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ColumnStats {
    pub name: String,
    pub detected_type: String,
    pub null_count: usize,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub mean: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CsvPreflightResult {
    pub row_count: usize,
    pub column_names: Vec<String>,
    pub columns: HashMap<String, ColumnStats>,
    pub is_valid_for_modeling: bool,
    pub validation_errors: Vec<String>,
    pub date_min: Option<String>,
    pub date_max: Option<String>,
}

pub fn sniff_and_validate_csv(
    bytes: &[u8],
    date_col: Option<&str>,
    target_col: Option<&str>,
    channel_cols: Option<&[&str]>,
) -> Result<CsvPreflightResult, String> {
    let mut reader = csv::ReaderBuilder::new()
        .has_headers(true)
        .flexible(true)
        .from_reader(bytes);

    let headers = reader
        .headers()
        .map_err(|e| format!("Failed to parse CSV headers: {e}"))?
        .clone();

    let column_names: Vec<String> = headers.iter().map(|s| s.trim().to_string()).collect();
    let col_indices: HashMap<String, usize> = column_names
        .iter()
        .enumerate()
        .map(|(i, name)| (name.clone(), i))
        .collect();

    let mut validation_errors = Vec::new();

    // Check required columns if provided
    if let Some(dc) = date_col {
        if !col_indices.contains_key(dc) {
            validation_errors.push(format!("Missing date column: '{dc}'"));
        }
    }
    if let Some(tc) = target_col {
        if !col_indices.contains_key(tc) {
            validation_errors.push(format!("Missing target column: '{tc}'"));
        }
    }
    if let Some(channels) = channel_cols {
        for &ch in channels {
            if !col_indices.contains_key(ch) {
                validation_errors.push(format!("Missing channel column: '{ch}'"));
            }
        }
    }

    let mut row_count = 0;
    let mut col_nulls = vec![0usize; column_names.len()];
    let mut col_sums = vec![0.0f64; column_names.len()];
    let mut col_mins = vec![f64::INFINITY; column_names.len()];
    let mut col_maxs = vec![f64::NEG_INFINITY; column_names.len()];
    let mut col_numeric_counts = vec![0usize; column_names.len()];
    let mut min_date: Option<String> = None;
    let mut max_date: Option<String> = None;

    let date_idx = date_col.and_then(|d| col_indices.get(d).copied());
    let target_idx = target_col.and_then(|t| col_indices.get(t).copied());
    let channel_indices: Vec<usize> = channel_cols
        .map(|chs| {
            chs.iter()
                .filter_map(|c| col_indices.get(*c).copied())
                .collect()
        })
        .unwrap_or_default();

    for result in reader.records() {
        let record = result.map_err(|e| format!("CSV read error at row {}: {e}", row_count + 1))?;
        row_count += 1;

        // Process columns
        for (i, field) in record.iter().enumerate() {
            if i >= column_names.len() {
                continue;
            }
            let trimmed = field.trim();
            if trimmed.is_empty()
                || trimmed.eq_ignore_ascii_case("nan")
                || trimmed.eq_ignore_ascii_case("null")
            {
                col_nulls[i] += 1;
            } else if let Ok(val) = trimmed.parse::<f64>() {
                col_numeric_counts[i] += 1;
                col_sums[i] += val;
                if val < col_mins[i] {
                    col_mins[i] = val;
                }
                if val > col_maxs[i] {
                    col_maxs[i] = val;
                }
            }
        }

        // Validate date if date_idx present
        if let Some(d_idx) = date_idx {
            if let Some(val) = record.get(d_idx) {
                let trimmed = val.trim();
                if !trimmed.is_empty() {
                    match &min_date {
                        None => min_date = Some(trimmed.to_string()),
                        Some(cur_min) if trimmed < cur_min.as_str() => {
                            min_date = Some(trimmed.to_string())
                        }
                        _ => {}
                    }
                    match &max_date {
                        None => max_date = Some(trimmed.to_string()),
                        Some(cur_max) if trimmed > cur_max.as_str() => {
                            max_date = Some(trimmed.to_string())
                        }
                        _ => {}
                    }
                }
            }
        }
    }

    // Minimum sample size requirement (PyMC-Marketing MMM requires at least 20 observations)
    if row_count < 14 {
        validation_errors.push(format!(
            "Dataset has only {row_count} rows; MMM modeling requires at least 14 rows"
        ));
    }

    // Target checks
    if let Some(t_idx) = target_idx {
        if col_nulls[t_idx] > 0 {
            validation_errors.push(format!(
                "Target column contains {} missing values",
                col_nulls[t_idx]
            ));
        }
        if col_numeric_counts[t_idx] + col_nulls[t_idx] < row_count {
            validation_errors.push("Target column contains non-numeric values".to_string());
        }
    }

    // Channel checks (non-negative spend)
    for &ch_idx in &channel_indices {
        let ch_name = &column_names[ch_idx];
        if col_mins[ch_idx] < 0.0 {
            validation_errors.push(format!(
                "Channel column '{ch_name}' contains negative spend: {}",
                col_mins[ch_idx]
            ));
        }
        if col_nulls[ch_idx] > 0 {
            validation_errors.push(format!(
                "Channel column '{ch_name}' contains {} missing values",
                col_nulls[ch_idx]
            ));
        }
    }

    let mut columns = HashMap::new();
    for (i, name) in column_names.iter().enumerate() {
        let is_num =
            col_numeric_counts[i] > 0 && (col_numeric_counts[i] + col_nulls[i] == row_count);
        let detected_type = if date_idx == Some(i) {
            "date".to_string()
        } else if is_num {
            "numeric".to_string()
        } else {
            "string".to_string()
        };

        let min = if col_numeric_counts[i] > 0 {
            Some(col_mins[i])
        } else {
            None
        };
        let max = if col_numeric_counts[i] > 0 {
            Some(col_maxs[i])
        } else {
            None
        };
        let mean = if col_numeric_counts[i] > 0 {
            Some(col_sums[i] / (col_numeric_counts[i] as f64))
        } else {
            None
        };

        columns.insert(
            name.clone(),
            ColumnStats {
                name: name.clone(),
                detected_type,
                null_count: col_nulls[i],
                min,
                max,
                mean,
            },
        );
    }

    let is_valid_for_modeling = validation_errors.is_empty();

    Ok(CsvPreflightResult {
        row_count,
        column_names,
        columns,
        is_valid_for_modeling,
        validation_errors,
        date_min: min_date,
        date_max: max_date,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sniff_valid_csv() {
        let csv_data = b"date,sales,tv,radio\n\
2023-01-01,100.0,10.0,5.0\n\
2023-01-08,120.0,15.0,7.0\n\
2023-01-15,110.0,12.0,6.0\n\
2023-01-22,130.0,18.0,8.0\n\
2023-01-29,140.0,20.0,9.0\n\
2023-02-05,150.0,22.0,10.0\n\
2023-02-12,160.0,25.0,11.0\n\
2023-02-19,170.0,28.0,12.0\n\
2023-02-26,180.0,30.0,13.0\n\
2023-03-05,190.0,32.0,14.0\n\
2023-03-12,200.0,35.0,15.0\n\
2023-03-19,210.0,38.0,16.0\n\
2023-03-26,220.0,40.0,17.0\n\
2023-04-02,230.0,42.0,18.0\n";

        let chs = ["tv", "radio"];
        let res =
            sniff_and_validate_csv(csv_data, Some("date"), Some("sales"), Some(&chs)).unwrap();

        assert_eq!(res.row_count, 14);
        assert!(res.is_valid_for_modeling);
        assert!(res.validation_errors.is_empty());
        assert_eq!(res.column_names, vec!["date", "sales", "tv", "radio"]);
        assert_eq!(res.columns["sales"].null_count, 0);
        assert_eq!(res.columns["sales"].min, Some(100.0));
        assert_eq!(res.columns["sales"].max, Some(230.0));
    }

    #[test]
    fn test_sniff_negative_spend_rejection() {
        let mut rows = String::from("date,sales,tv\n");
        for i in 0..15 {
            let tv_spend = if i == 5 { -10.0 } else { 20.0 };
            rows.push_str(&format!("2023-01-{:02},100.0,{}\n", i + 1, tv_spend));
        }

        let chs = ["tv"];
        let res = sniff_and_validate_csv(rows.as_bytes(), Some("date"), Some("sales"), Some(&chs))
            .unwrap();

        assert!(!res.is_valid_for_modeling);
        assert!(res
            .validation_errors
            .iter()
            .any(|e| e.contains("negative spend")));
    }
}
