//! Fast MCMC convergence diagnostics and decision gate evaluation in Rust.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DiagnosticSummary {
    pub max_rhat: f64,
    pub min_ess: f64,
    pub divergences: usize,
    pub decision_status: String,
    pub decision_tools_enabled: bool,
    pub failures: Vec<String>,
    pub warnings: Vec<String>,
}

/// Compute split-chain R-hat for a single parameter across multiple MCMC chains.
/// Chains is a slice of chains, where each chain is a Vec of draws.
pub fn compute_split_rhat(chains: &[Vec<f64>]) -> f64 {
    if chains.is_empty() {
        return f64::NAN;
    }

    // Split each chain in half
    let mut split_chains: Vec<Vec<f64>> = Vec::new();
    for chain in chains {
        let n = chain.len();
        if n < 4 {
            split_chains.push(chain.clone());
        } else {
            let half = n / 2;
            split_chains.push(chain[..half].to_vec());
            split_chains.push(chain[half..].to_vec());
        }
    }

    let m = split_chains.len() as f64;
    let n = split_chains[0].len() as f64;
    if m <= 1.0 || n <= 1.0 {
        return 1.0;
    }

    // Calculate chain means
    let mut chain_means = Vec::with_capacity(split_chains.len());
    let mut chain_vars = Vec::with_capacity(split_chains.len());

    for ch in &split_chains {
        let sum: f64 = ch.iter().sum();
        let mean = sum / (ch.len() as f64);
        let var = ch.iter().map(|&x| (x - mean).powi(2)).sum::<f64>() / ((ch.len() - 1) as f64);
        chain_means.push(mean);
        chain_vars.push(var);
    }

    let overall_mean: f64 = chain_means.iter().sum::<f64>() / m;
    let b_over_n = chain_means.iter().map(|&x| (x - overall_mean).powi(2)).sum::<f64>() / (m - 1.0);
    let w: f64 = chain_vars.iter().sum::<f64>() / m;

    if w <= 1e-12 {
        return 1.0;
    }

    let var_plus = ((n - 1.0) / n) * w + b_over_n;
    (var_plus / w).sqrt()
}

/// Evaluate MCMC diagnostics across all parameters and divergence count.
pub fn evaluate_mcmc_gates(
    rhats: &[f64],
    esses: &[f64],
    divergences: usize,
) -> DiagnosticSummary {
    let mut max_rhat = 1.0f64;
    for &r in rhats {
        if r.is_finite() && r > max_rhat {
            max_rhat = r;
        }
    }

    let mut min_ess = f64::INFINITY;
    for &e in esses {
        if e.is_finite() && e < min_ess {
            min_ess = e;
        }
    }
    if min_ess.is_infinite() {
        min_ess = 1000.0;
    }

    let mut failures = Vec::new();
    let mut warnings = Vec::new();

    if divergences > 0 {
        failures.push(format!("Sampler had {divergences} divergent transition(s)"));
    }
    if max_rhat > 1.05 {
        failures.push(format!("Max R-hat ({max_rhat:.3}) exceeds safety threshold (1.05)"));
    } else if max_rhat > 1.02 {
        warnings.push(format!("Max R-hat ({max_rhat:.3}) shows mild convergence friction"));
    }

    if min_ess < 100.0 {
        failures.push(format!("Min Bulk-ESS ({min_ess:.1}) is below critical floor (100.0)"));
    } else if min_ess < 400.0 {
        warnings.push(format!("Min Bulk-ESS ({min_ess:.1}) is below recommended target (400.0)"));
    }

    let (decision_status, decision_tools_enabled) = if !failures.is_empty() {
        ("rejected".to_string(), false)
    } else if !warnings.is_empty() {
        ("caution".to_string(), true)
    } else {
        ("approved".to_string(), true)
    };

    DiagnosticSummary {
        max_rhat,
        min_ess,
        divergences,
        decision_status,
        decision_tools_enabled,
        failures,
        warnings,
    }
}
