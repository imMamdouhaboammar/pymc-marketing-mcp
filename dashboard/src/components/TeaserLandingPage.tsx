import React, { useState, useMemo } from 'react';
import {
  ShieldCheck,
  XCircle,
  Sliders,
  ArrowRight,
  Copy,
  Check,
  ExternalLink,
  Zap,
  BarChart3,
  Layers,
  Database,
  TrendingUp,
  Cpu,
} from 'lucide-react';

interface TeaserLandingPageProps {
  onOpenAuth: () => void;
}

interface DiagnosticPreset {
  id: string;
  name: string;
  badge: string;
  rhat: number;
  divergences: number;
  bfmi: number;
  summary: string;
}

const PRESETS: DiagnosticPreset[] = [
  {
    id: 'golden',
    name: 'Golden Production Run',
    badge: 'Approved',
    rhat: 1.01,
    divergences: 0,
    bfmi: 0.88,
    summary: 'Hamiltonian trajectories converged smoothly. All statistical criteria satisfied.',
  },
  {
    id: 'divergent',
    name: 'Pathological Curvature',
    badge: 'Blocked',
    rhat: 1.02,
    divergences: 14,
    bfmi: 0.35,
    summary: '14 divergences encountered. Energy distribution warped by step size.',
  },
  {
    id: 'cold_start',
    name: 'Cold Chain Failure',
    badge: 'Blocked',
    rhat: 1.18,
    divergences: 0,
    bfmi: 0.14,
    summary: 'Chains failed to mix across isolated posterior modes. R-hat exceeds safety limits.',
  },
];

interface CapabilityItem {
  name: string;
  tier: string;
  badge: 'stable' | 'preview' | 'experimental';
  purpose: string;
  exampleCall: string;
  exampleOutput: string;
}

const CAPABILITIES: Record<string, CapabilityItem[]> = {
  mmm: [
    {
      name: 'fit_mmm',
      tier: 'Bayesian MMM',
      badge: 'stable',
      purpose: 'Fits a hierarchical Marketing Mix Model with adstock and saturation transformations.',
      exampleCall: '{\n  "dataset_id": "ds_q3_us_omnichannel",\n  "target_column": "revenue",\n  "date_column": "week_start",\n  "channel_columns": ["search_spend", "social_spend", "video_spend"],\n  "adstock_max_lag": 8\n}',
      exampleOutput: '{\n  "model_id": "mmm_70f2a9",\n  "status": "fitted",\n  "chains": 4,\n  "draws_per_chain": 1000,\n  "gate_status": "unevaluated"\n}',
    },
    {
      name: 'diagnose_mmm',
      tier: 'Decision Gate',
      badge: 'stable',
      purpose: 'Executes the mandatory statistical gate checking R-hat, divergences, and BFMI.',
      exampleCall: '{\n  "model_id": "mmm_70f2a9",\n  "max_rhat_threshold": 1.05,\n  "max_divergences_allowed": 0,\n  "min_bfmi_threshold": 0.20\n}',
      exampleOutput: '{\n  "model_id": "mmm_70f2a9",\n  "verdict": "pass",\n  "max_rhat": 1.012,\n  "divergences": 0,\n  "min_bfmi": 0.884,\n  "decision_support_approved": true\n}',
    },
    {
      name: 'calibrate_mmm',
      tier: 'Scientific Lift',
      badge: 'preview',
      purpose: 'Calibrates MMM posterior distributions against randomized geo lift experiment results.',
      exampleCall: '{\n  "model_id": "mmm_70f2a9",\n  "lift_test_id": "lift_geo_q3_social",\n  "channel": "social_spend",\n  "incremental_lift_dollars": 142000\n}',
      exampleOutput: '{\n  "model_id": "mmm_70f2a9_calibrated",\n  "prior_updated": true,\n  "posterior_shift_pct": 12.4\n}',
    },
  ],
  decisions: [
    {
      name: 'optimize_budget',
      tier: 'Resource Allocation',
      badge: 'stable',
      purpose: 'Computes optimal channel budget allocations under posterior parameter uncertainty.',
      exampleCall: '{\n  "model_id": "mmm_70f2a9",\n  "total_budget": 500000,\n  "time_horizon_weeks": 12,\n  "channel_constraints": {\n    "search_spend": {"min": 80000, "max": 250000},\n    "social_spend": {"min": 60000, "max": 200000}\n  }\n}',
      exampleOutput: '{\n  "expected_revenue": 2184000,\n  "ci_90_lower": 1940000,\n  "ci_90_upper": 2420000,\n  "allocations": {\n    "search_spend": 215000,\n    "social_spend": 165000,\n    "video_spend": 120000\n  }\n}',
    },
    {
      name: 'optimize_flighting',
      tier: 'Weekly Scheduling',
      badge: 'preview',
      purpose: 'Schedules weekly media spend pulses while accounting for carryover decay curves.',
      exampleCall: '{\n  "model_id": "mmm_70f2a9",\n  "weeks": 8,\n  "weekly_ceiling": 60000\n}',
      exampleOutput: '{\n  "schedule": [\n    {"week": 1, "spend": 45000},\n    {"week": 2, "spend": 58000}\n  ],\n  "efficiency_gain_pct": 8.7\n}',
    },
    {
      name: 'get_incremental_roas',
      tier: 'Marginal Return',
      badge: 'stable',
      purpose: 'Returns marginal returns per dollar spent across posterior parameter credible bands.',
      exampleCall: '{\n  "model_id": "mmm_70f2a9",\n  "channel": "search_spend"\n}',
      exampleOutput: '{\n  "mean_mroas": 3.84,\n  "hdi_3_pct": 3.12,\n  "hdi_97_pct": 4.56\n}',
    },
  ],
  clv: [
    {
      name: 'fit_purchase_model',
      tier: 'Customer Dynamics',
      badge: 'stable',
      purpose: 'Fits BG/NBD transactional repeat purchase frequency and dropout hazard models.',
      exampleCall: '{\n  "dataset_id": "ds_clv_transactions",\n  "customer_id_col": "user_id",\n  "datetime_col": "order_date"\n}',
      exampleOutput: '{\n  "model_id": "clv_freq_88a",\n  "active_users": 48200,\n  "expected_purchases_next_90d": 1.42\n}',
    },
    {
      name: 'fit_value_model',
      tier: 'Monetary Modeling',
      badge: 'stable',
      purpose: 'Fits Gamma-Gamma monetary value model conditioned on repeat purchases.',
      exampleCall: '{\n  "dataset_id": "ds_clv_transactions",\n  "monetary_col": "basket_revenue"\n}',
      exampleOutput: '{\n  "model_id": "clv_val_88b",\n  "expected_average_order_value": 78.40\n}',
    },
    {
      name: 'estimate_customer_lifetime_value',
      tier: 'Valuation',
      badge: 'stable',
      purpose: 'Combines frequency and monetary models with cost of capital discount curves.',
      exampleCall: '{\n  "frequency_model_id": "clv_freq_88a",\n  "monetary_model_id": "clv_val_88b",\n  "time_months": 12,\n  "discount_rate": 0.08\n}',
      exampleOutput: '{\n  "mean_clv": 248.50,\n  "cohort_value": 11980000\n}',
    },
  ],
  provenance: [
    {
      name: 'submit_fit_mmm_job',
      tier: 'Durable Compute',
      badge: 'stable',
      purpose: 'Launches asynchronous MCMC sampling with durable job tracking and state recovery.',
      exampleCall: '{\n  "dataset_id": "ds_q3_us_omnichannel",\n  "target_column": "revenue",\n  "chains": 4,\n  "draws": 2000\n}',
      exampleOutput: '{\n  "job_id": "job_mmm_9921ef",\n  "status": "queued",\n  "stream_uri": "marketing://jobs/job_mmm_9921ef"\n}',
    },
    {
      name: 'marketing:// resources',
      tier: 'MCP Provenance',
      badge: 'stable',
      purpose: 'Inspects immutable dataset snapshots, diagnostic reports, and posterior plots.',
      exampleCall: '{\n  "uri": "marketing://models/mmm_70f2a9/diagnostics"\n}',
      exampleOutput: '{\n  "status": "passed",\n  "rhat_max": 1.01,\n  "evaluated_at": "2026-10-16T10:00:00Z"\n}',
    },
  ],
};

const FAQS = [
  {
    q: 'Why can not an LLM agent write PyMC code directly?',
    a: 'Language models produce plausible Python scripts but fail to interpret high-dimensional Hamiltonian energy paths reliably. An unguided agent will silently ignore 50 divergent transitions, treat cold-chain estimates as empirical truth, and allocate five hundred thousand dollars on invalid math. PyMC Marketing MCP acts as an unyielding statistical runtime gate between agent prompts and capital decisions.',
  },
  {
    q: 'What occurs when a fitted model fails the diagnostic gate?',
    a: 'The server records the failure in the metadata registry and flags the model as blocked for decision support. Any subsequent agent request to run simulate_budget, optimize_budget, or optimize_flighting is rejected at the protocol boundary. The agent is forced to either collect cleaner data, relax uncalibrated priors, or gather experimental lift evidence.',
  },
  {
    q: 'Does this MCP server execute live ad buys on Google Ads or Meta Ads?',
    a: 'No. The project deliberately refuses to execute uncontrolled live bidding. It owns scientific decision safety, validation, MCMC sampling, and mathematically optimal budget schedules. The verified flighting schedule can then be approved by a human or dispatched through dedicated ad APIs.',
  },
  {
    q: 'How is multi-tenant isolation enforced?',
    a: 'Every storage query and metadata lookup requires an organization identifier. Models, datasets, diagnostic verdicts, and background jobs are scoped strictly to the authenticated organization. Cross-tenant reads fail closed at the database layer.',
  },
  {
    q: 'What happens if a long MCMC sampling job restarts or crashes?',
    a: 'Sampling jobs run under a durable state machine. If an instance restarts, workers recover using transactional checkpoints and physical artifact verification. Incomplete or cancelled jobs cannot transition into false completed states.',
  },
];

export const TeaserLandingPage: React.FC<TeaserLandingPageProps> = ({ onOpenAuth }) => {
  const [selectedPreset, setSelectedPreset] = useState<string>('golden');
  const [rhat, setRhat] = useState<number>(1.01);
  const [divergences, setDivergences] = useState<number>(0);
  const [bfmi, setBfmi] = useState<number>(0.88);

  const [activeCategory, setActiveCategory] = useState<string>('mmm');
  const [selectedToolIndex, setSelectedToolIndex] = useState<number>(0);

  const [copiedConfig, setCopiedConfig] = useState<string | null>(null);
  const [activeClientTab, setActiveClientTab] = useState<'claude' | 'cursor' | 'gemini'>('claude');

  const applyPreset = (preset: DiagnosticPreset) => {
    setSelectedPreset(preset.id);
    setRhat(preset.rhat);
    setDivergences(preset.divergences);
    setBfmi(preset.bfmi);
  };

  const gateResult = useMemo(() => {
    const rhatOk = rhat <= 1.05;
    const divOk = divergences === 0;
    const bfmiOk = bfmi >= 0.2;

    if (rhatOk && divOk && bfmiOk) {
      return {
        verdict: 'PASS',
        badgeBg: 'bg-emerald-50 border-emerald-200 text-emerald-700',
        decisionAllowed: true,
        message: 'Statistical criteria satisfied. Model approved for budget allocation.',
      };
    }

    if (divergences > 0) {
      return {
        verdict: 'BLOCK',
        badgeBg: 'bg-[#FFF4ED] border-[#FFE8D6] text-[#FF6A2C]',
        decisionAllowed: false,
        message: `${divergences} divergences encountered. Hamiltonian geometry corrupted.`,
      };
    }

    if (!rhatOk) {
      return {
        verdict: 'BLOCK',
        badgeBg: 'bg-[#FFF4ED] border-[#FFE8D6] text-[#FF6A2C]',
        decisionAllowed: false,
        message: `R-hat (${rhat.toFixed(2)}) exceeds 1.05 limit. Chains have not converged.`,
      };
    }

    return {
      verdict: 'CAUTION',
      badgeBg: 'bg-amber-50 border-amber-200 text-amber-700',
      decisionAllowed: false,
      message: `Energy BFMI (${bfmi.toFixed(2)}) is below 0.20. Incomplete distribution coverage.`,
    };
  }, [rhat, divergences, bfmi]);

  const copySnippet = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedConfig(id);
    setTimeout(() => setCopiedConfig(null), 2000);
  };

  const currentToolList = CAPABILITIES[activeCategory] || [];
  const currentTool = currentToolList[selectedToolIndex] || currentToolList[0];

  const claudeConfig = JSON.stringify(
    {
      mcpServers: {
        'pymc-marketing': {
          command: 'uv',
          args: ['run', '--directory', '/path/to/pymc-marketing-mcp', 'marketing-mcp', '--transport', 'stdio'],
        },
      },
    },
    null,
    2
  );

  const cursorConfig = JSON.stringify(
    {
      mcpServers: {
        'pymc-marketing': {
          url: 'https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp',
          headers: {
            Authorization: 'Bearer YOUR_API_KEY',
          },
        },
      },
    },
    null,
    2
  );

  const geminiCommand = 'uv run marketing-mcp --transport stdio';

  return (
    <div className="flex flex-col bg-[#FFFFFF] text-[#0A0A0A] font-['Inter',sans-serif]">
      {/* 0. PROMO BANNER (PREPILOT STYLE) */}
      <div className="bg-[#FFF4ED] border-b border-[#FFE8D6] py-2.5 px-4 text-center">
        <div className="max-w-[1240px] mx-auto flex items-center justify-center space-x-2 text-xs text-[#0A0A0A]">
          <span className="font-semibold text-[#FF6A2C]">⚡ PrePilot Performance Partner:</span>
          <span className="text-[#1A1A1A]">Decision-safe Bayesian marketing science for autonomous agents.</span>
          <a
            href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp"
            target="_blank"
            rel="noreferrer"
            className="hidden sm:inline-flex font-semibold text-[#FF6A2C] underline decoration-[#FF8A47] hover:text-[#FF8A47] ml-2"
          >
            Read GitHub Spec →
          </a>
        </div>
      </div>

      {/* 1. ABOVE-THE-FOLD HERO (PREPILOT TYPOGRAPHY & LAYOUT) */}
      <section className="relative overflow-hidden pt-16 pb-20 bg-gradient-to-b from-[#FAFAF7] via-[#FFFFFF] to-[#FAFAF7] border-b border-[#ECECEC]">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
            {/* Top Pill */}
            <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-white border border-[#ECECEC] text-xs font-mono text-[#0A0A0A] mb-8 shadow-sm">
              <span className="w-2 h-2 rounded-full bg-[#FF6A2C] animate-pulse"></span>
              <span className="font-semibold text-[#FF6A2C]">MCP Protocol 2.x</span>
              <span className="text-[#D0D0CE]">·</span>
              <span className="text-[#6B6B6B]">83 Automated Contract Tests Green</span>
            </div>

            {/* Headline with PrePilot Character Badge */}
            <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-[#0A0A0A] mb-6 leading-[1.12] font-['Outfit']">
              <span>Get decision-safe marketing science</span>{' '}
              <span className="inline-block align-middle ml-2">
                <svg className="w-10 h-10 inline-block" viewBox="0 0 32 32" fill="none" aria-hidden="true">
                  <rect x="4" y="8" width="24" height="16" rx="5" fill="#FFE8D6" stroke="#FFB088" strokeWidth="1.5" />
                  <circle cx="11" cy="16" r="2.2" fill="#FF6A2C" />
                  <circle cx="21" cy="16" r="2.2" fill="#FF6A2C" />
                  <path d="M14 19h4" stroke="#FF6A2C" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </span>
              <br />
              <span className="text-[#0A0A0A]">from Claude & ChatGPT</span>
            </h1>

            {/* Subheadline with Newsreader Italic Accent */}
            <p className="text-lg sm:text-xl text-[#6B6B6B] max-w-3xl mb-10 leading-relaxed font-normal">
              PyMC Marketing MCP gives your AI <em className="text-[#0A0A0A] font-serif not-italic font-normal">verified Bayesian MMM</em>, customer lifetime value, and hard statistical gates that refuse hallucinated media spend.
            </p>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row items-center gap-3.5 w-full sm:w-auto mb-6">
              <button
                onClick={onOpenAuth}
                className="w-full sm:w-auto flex items-center justify-center space-x-2 px-7 py-3.5 bg-[#FF6A2C] hover:bg-[#FF8A47] text-white font-semibold text-sm rounded-xl shadow-[0_4px_14px_rgba(255,106,44,0.35)] transition-all active:scale-[0.99]"
              >
                <span>Launch Developer Console</span>
                <ArrowRight className="w-4 h-4" />
              </button>

              <a
                href="#simulator"
                className="w-full sm:w-auto flex items-center justify-center space-x-2 px-6 py-3.5 bg-white hover:bg-[#FAFAF7] border border-[#ECECEC] text-[#0A0A0A] font-semibold text-sm rounded-xl transition-colors shadow-sm"
              >
                <Sliders className="w-4 h-4 text-[#FF6A2C]" />
                <span>Test Decision Gate</span>
              </a>

              <a
                href="#quickstart"
                className="w-full sm:w-auto flex items-center justify-center space-x-2 px-6 py-3.5 bg-[#101828] hover:bg-[#1D2939] text-white font-medium text-sm rounded-xl transition-colors shadow-sm"
              >
                <Zap className="w-4 h-4 text-[#FFB84D]" />
                <span>Add in 1 Click</span>
              </a>
            </div>

            {/* Micro Trust */}
            <div className="text-xs text-[#6B6B6B] font-mono">
              No prompt engineering · Works inside Claude & ChatGPT · Strict multi-tenant isolation
            </div>
          </div>

          {/* Hero Visual Card: Split Comparison */}
          <div className="mt-14 max-w-4xl mx-auto rounded-2xl border border-[#ECECEC] bg-white p-3 sm:p-5 shadow-[0_12px_40px_-8px_rgba(15,15,15,0.08)]">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Unchecked Agent */}
              <div className="p-5 rounded-xl bg-[#FFF8F7] border border-rose-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-rose-700 flex items-center space-x-1.5">
                      <XCircle className="w-4 h-4 text-rose-500" />
                      <span>Standard Unchecked Agent</span>
                    </span>
                    <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-rose-100 text-rose-700 border border-rose-200">
                      Hallucination Risk
                    </span>
                  </div>
                  <p className="text-xs text-[#6B6B6B] mb-4 leading-relaxed">
                    The model fits an arbitrary polynomial curve in Python, ignores 18 divergent trajectories, and dispatches a $250,000 budget reallocation.
                  </p>
                  <div className="p-3 bg-white rounded-lg border border-rose-200 text-[11px] font-mono text-zinc-600 space-y-1">
                    <div className="text-rose-600 font-semibold">Warning: 18 divergences encountered</div>
                    <div className="text-zinc-500">R-hat: 1.14 (convergence failed)</div>
                    <div className="text-rose-700 pt-1 font-semibold">Action: $250k budget shifted on false signals</div>
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-rose-200/60 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-rose-700">Verdict: Capital Misallocation</span>
                  <span className="text-rose-600 font-bold">REJECTED</span>
                </div>
              </div>

              {/* PyMC Marketing MCP */}
              <div className="p-5 rounded-xl bg-[#F0FDF4] border border-emerald-200 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold text-emerald-800 flex items-center space-x-1.5">
                      <ShieldCheck className="w-4 h-4 text-emerald-600" />
                      <span>PyMC Marketing MCP</span>
                    </span>
                    <span className="text-[10px] font-mono font-medium px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                      Decision-Safe Gate
                    </span>
                  </div>
                  <p className="text-xs text-[#6B6B6B] mb-4 leading-relaxed">
                    The runtime server intercepts the request. The diagnostic gate inspects energy paths and locks downstream optimization until criteria pass.
                  </p>
                  <div className="p-3 bg-white rounded-lg border border-emerald-200 text-[11px] font-mono text-zinc-700 space-y-1">
                    <div className="text-emerald-700 font-semibold">Gelman-Rubin R-hat: 1.01 (converged)</div>
                    <div className="text-emerald-700 font-semibold">Divergences: 0 (zero tolerance)</div>
                    <div className="text-emerald-800 pt-1 font-semibold">Action: Approved. Causal ROAS unlocked</div>
                  </div>
                </div>
                <div className="mt-4 pt-3 border-t border-emerald-200/60 flex items-center justify-between text-[11px] font-mono">
                  <span className="text-emerald-700">Verdict: Statistically Bounded</span>
                  <span className="text-emerald-600 font-bold">PROTECTED</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 2. INFINITE MARQUEE TICKER (PREPILOT STYLE) */}
      <div className="py-4 border-b border-[#ECECEC] bg-white overflow-hidden" aria-label="Capabilities ticker">
        <div className="animate-marquee whitespace-nowrap text-xs font-mono font-medium text-[#6B6B6B]">
          <span className="mx-4 text-[#0A0A0A] font-semibold">Built for performance marketers & AI agents</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">Works inside Claude & Cursor & ChatGPT</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">Decision-safe Bayesian MMM</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">Gelman-Rubin R-hat &le; 1.05 gate</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">Zero Divergence Leapfrog Safety</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">Incremental ROAS & budget allocation</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">CLV BG/NBD & Gamma-Gamma</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">12 MCP tools & resources</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">83 automated contract tests</span>
          <span className="text-[#FF6A2C]">·</span>
          {/* Duplicate loop */}
          <span className="mx-4 text-[#0A0A0A] font-semibold">Built for performance marketers & AI agents</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">Works inside Claude & Cursor & ChatGPT</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">Decision-safe Bayesian MMM</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">Gelman-Rubin R-hat &le; 1.05 gate</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">Zero Divergence Leapfrog Safety</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">Incremental ROAS & budget allocation</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">CLV BG/NBD & Gamma-Gamma</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4">12 MCP tools & resources</span>
          <span className="text-[#FF6A2C]">·</span>
          <span className="mx-4 text-[#0A0A0A] font-semibold">83 automated contract tests</span>
          <span className="text-[#FF6A2C]">·</span>
        </div>
      </div>

      {/* 3. MASCOT STRIP / WORKFLOW PERSONAS */}
      <section className="py-12 border-b border-[#ECECEC] bg-[#FAFAF7]">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="text-center mb-6">
            <span className="text-xs font-mono uppercase tracking-wider text-[#FF6A2C] font-semibold">
              Specialized Agent Roles
            </span>
            <h3 className="text-lg font-bold text-[#0A0A0A] font-['Outfit'] mt-1">
              Autonomous workflows grounded in statistical discipline
            </h3>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6">
            {[
              { id: '01', role: 'MMM Lead', task: 'Directs full modeling run', icon: BarChart3, color: 'bg-[#FFF4ED] text-[#FF6A2C] border-[#FFE8D6]' },
              { id: '02', role: 'Bayesian Statistician', task: 'Verifies R-hat & BFMI', icon: ShieldCheck, color: 'bg-[#E0EBFF] text-[#1E5BC6] border-[#B8D1FF]' },
              { id: '03', role: 'Media Planner', task: 'Computes adstock curves', icon: TrendingUp, color: 'bg-[#EDE4FF] text-[#6D4FE0] border-[#DDD6FE]' },
              { id: '04', role: 'Lift Calibration', task: 'Anchors to geo experiments', icon: Layers, color: 'bg-[#FEF3C7] text-[#D97706] border-[#FDE68A]' },
              { id: '05', role: 'Budget Allocator', task: 'Solves optimal flighting', icon: Cpu, color: 'bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]' },
              { id: '06', role: 'CLV Modeler', task: 'Evaluates customer cohorts', icon: Database, color: 'bg-[#FDF2F8] text-[#DB2777] border-[#FBCFE8]' },
            ].map((persona) => {
              const IconComp = persona.icon;
              return (
                <div
                  key={persona.id}
                  className="flex items-center space-x-3 p-3 rounded-2xl bg-white border border-[#ECECEC] shadow-sm hover:border-[#FF6A2C]/50 transition-all cursor-default"
                >
                  <div className={`w-10 h-10 rounded-xl border flex items-center justify-center ${persona.color}`}>
                    <IconComp className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-xs font-bold text-[#0A0A0A] font-['Outfit']">{persona.role}</div>
                    <div className="text-[11px] text-[#6B6B6B]">{persona.task}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* 4. HOW IT WORKS (3-STEP NUMBERED SEQUENCE) */}
      <section id="how" className="py-20 border-b border-[#ECECEC] bg-white">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mb-14">
            <span className="text-xs font-mono uppercase tracking-wider text-[#FF6A2C] font-semibold">
              Three Step Guardrail
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0A0A0A] tracking-tight font-['Outfit'] mt-1">
              Talk to it like a teammate. <em className="text-[#6B6B6B] font-serif not-italic font-normal">Get statistically verified work.</em>
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            <div className="p-8 rounded-2xl bg-[#FAFAF7] border border-[#ECECEC] relative">
              <div className="text-3xl font-extrabold text-[#FF6A2C] font-mono mb-4">01</div>
              <h3 className="text-lg font-bold text-[#0A0A0A] font-['Outfit'] mb-2">Connect once</h3>
              <p className="text-xs text-[#6B6B6B] leading-relaxed">
                Add PyMC Marketing MCP to Claude or Cursor through standard JSON-RPC. Two minutes, zero local model code to write.
              </p>
            </div>

            <div className="p-8 rounded-2xl bg-[#FAFAF7] border border-[#ECECEC] relative">
              <div className="text-3xl font-extrabold text-[#FF6A2C] font-mono mb-4">02</div>
              <h3 className="text-lg font-bold text-[#0A0A0A] font-['Outfit'] mb-2">Brief in plain English</h3>
              <p className="text-xs text-[#6B6B6B] leading-relaxed">
                Ask your agent: "Allocate $500k across search, social, and video with an 8-week adstock horizon." The agent calls the verified schema.
              </p>
            </div>

            <div className="p-8 rounded-2xl bg-[#FAFAF7] border border-[#ECECEC] relative">
              <div className="text-3xl font-extrabold text-[#FF6A2C] font-mono mb-4">03</div>
              <h3 className="text-lg font-bold text-[#0A0A0A] font-['Outfit'] mb-2">Get decision-safe outputs</h3>
              <p className="text-xs text-[#6B6B6B] leading-relaxed">
                The statistical gate inspects MCMC energy paths. Budget tools refuse execution if the model diverges, protecting your capital.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. THE CORE INVARIANT (GATE RULES) */}
      <section id="gate" className="py-20 border-b border-[#ECECEC] bg-[#FAFAF7]">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="flex flex-col lg:flex-row items-center gap-12">
            <div className="flex-1">
              <div className="inline-flex items-center space-x-2 text-xs font-mono text-[#FF6A2C] font-semibold mb-3">
                <ShieldCheck className="w-4 h-4" />
                <span>The Core Operating Invariant</span>
              </div>
              <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0A0A0A] tracking-tight font-['Outfit'] mb-4">
                Model fitted does not mean model approved for decisions.
              </h2>
              <p className="text-sm text-[#6B6B6B] leading-relaxed mb-8">
                Fitting a model produces posterior samples. It does not validate their statistical integrity. Our runtime enforces this invariant through an automated diagnostic gate before downstream budget tools can execute.
              </p>

              <div className="space-y-4">
                <div className="p-5 rounded-2xl bg-white border border-[#ECECEC] shadow-sm flex items-start space-x-4">
                  <div className="w-8 h-8 rounded-xl bg-[#FFF4ED] text-[#FF6A2C] font-mono font-bold text-xs flex items-center justify-center border border-[#FFE8D6]">
                    01
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#0A0A0A] font-['Outfit']">Gelman-Rubin Convergence (R-hat &le; 1.05)</h3>
                    <p className="text-xs text-[#6B6B6B] mt-1 leading-relaxed">
                      Verifies that multiple independent Hamiltonian Markov chains converged on the same posterior mode.
                    </p>
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-white border border-[#ECECEC] shadow-sm flex items-start space-x-4">
                  <div className="w-8 h-8 rounded-xl bg-[#FFF4ED] text-[#FF6A2C] font-mono font-bold text-xs flex items-center justify-center border border-[#FFE8D6]">
                    02
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#0A0A0A] font-['Outfit']">Zero Divergent Transitions</h3>
                    <p className="text-xs text-[#6B6B6B] mt-1 leading-relaxed">
                      Enforces zero divergences. Any geometric breakdown during leapfrog integration invalidates decision support.
                    </p>
                  </div>
                </div>

                <div className="p-5 rounded-2xl bg-white border border-[#ECECEC] shadow-sm flex items-start space-x-4">
                  <div className="w-8 h-8 rounded-xl bg-[#FFF4ED] text-[#FF6A2C] font-mono font-bold text-xs flex items-center justify-center border border-[#FFE8D6]">
                    03
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#0A0A0A] font-['Outfit']">Energy Fraction of Missing Information (BFMI &ge; 0.20)</h3>
                    <p className="text-xs text-[#6B6B6B] mt-1 leading-relaxed">
                      Guarantees that the momentum distribution sampled the target energy states thoroughly.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Circuit Card */}
            <div className="flex-1 w-full">
              <div className="p-8 rounded-2xl bg-white border border-[#ECECEC] shadow-lg">
                <div className="flex items-center justify-between pb-4 mb-6 border-b border-[#ECECEC]">
                  <span className="font-['Outfit'] font-bold text-sm text-[#0A0A0A]">Decision Gate Pipeline</span>
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-[#FFF4ED] text-[#FF6A2C] border border-[#FFE8D6]">
                    Hard Runtime Block
                  </span>
                </div>

                <div className="space-y-4 text-xs font-mono">
                  <div className="p-3.5 rounded-xl bg-[#FAFAF7] border border-[#ECECEC] text-[#0A0A0A] flex items-center space-x-3">
                    <span className="text-[#FF6A2C] font-bold">1</span>
                    <span>Agent calls: optimize_budget($500k)</span>
                  </div>
                  <div className="text-center text-[#A0A0A0]">↓</div>
                  <div className="p-3.5 rounded-xl bg-[#FAFAF7] border border-[#ECECEC] text-[#0A0A0A] flex items-center space-x-3">
                    <span className="text-[#FF6A2C] font-bold">2</span>
                    <span>Server inspects model diagnostics in DB</span>
                  </div>
                  <div className="text-center text-[#A0A0A0]">↓</div>
                  <div className="p-3.5 rounded-xl bg-[#FFF4ED] border border-[#FFE8D6] text-[#FF6A2C] font-semibold flex items-center justify-between">
                    <span>3. Evaluate criteria</span>
                    <span>R-hat &le; 1.05 & div == 0</span>
                  </div>
                  <div className="text-center text-[#A0A0A0]">↓</div>
                  <div className="p-3.5 rounded-xl bg-white border border-[#ECECEC] text-[#0A0A0A] flex items-center justify-between shadow-sm">
                    <span className="font-bold">4. Downstream Status:</span>
                    <span className="text-emerald-600 font-bold">Approved / Blocked</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. INTERACTIVE MCMC DIAGNOSTIC SIMULATOR (REACT ARIA ACCESSIBLE) */}
      <section id="simulator" className="py-20 border-b border-[#ECECEC] bg-white">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono uppercase tracking-wider text-[#FF6A2C] font-semibold">
              Live Interactive Prototype
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0A0A0A] tracking-tight font-['Outfit'] mt-1">
              Experience the Diagnostic Decision Gate
            </h2>
            <p className="text-sm text-[#6B6B6B] mt-2 leading-relaxed">
              Tweak Hamiltonian parameters or choose presets below. Observe how the server dynamically admits or blocks downstream budget optimization.
            </p>
          </div>

          <div className="max-w-3xl mx-auto bg-[#FAFAF7] border border-[#ECECEC] rounded-2xl p-6 sm:p-10 shadow-lg">
            {/* Presets */}
            <div className="mb-8">
              <span className="text-xs font-mono text-[#6B6B6B] block mb-3 font-semibold">Diagnostic Presets:</span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => applyPreset(preset)}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      selectedPreset === preset.id
                        ? 'bg-white border-[#FF6A2C] text-[#0A0A0A] shadow-sm'
                        : 'bg-white/80 border-[#ECECEC] text-[#6B6B6B] hover:text-[#0A0A0A] hover:border-[#D0D0D0]'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-xs font-bold font-['Outfit']">{preset.name}</span>
                      <span
                        className={`text-[9px] font-mono px-2 py-0.5 rounded-full font-semibold border ${
                          preset.badge === 'Approved'
                            ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                            : 'bg-[#FFF4ED] border-[#FFE8D6] text-[#FF6A2C]'
                        }`}
                      >
                        {preset.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#6B6B6B] leading-tight">{preset.summary}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Sliders */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8 p-6 bg-white rounded-xl border border-[#ECECEC]">
              {/* Rhat */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label htmlFor="rhat-range" className="text-xs font-mono font-medium text-[#0A0A0A]">
                    Max R-hat (&le; 1.05)
                  </label>
                  <span className={`text-xs font-mono font-bold ${rhat <= 1.05 ? 'text-emerald-600' : 'text-[#FF6A2C]'}`}>
                    {rhat.toFixed(2)}
                  </span>
                </div>
                <input
                  id="rhat-range"
                  type="range"
                  min="0.99"
                  max="1.30"
                  step="0.01"
                  value={rhat}
                  aria-label="Gelman-Rubin R-hat threshold"
                  aria-valuemin={0.99}
                  aria-valuemax={1.30}
                  aria-valuenow={rhat}
                  onChange={(e) => {
                    setRhat(parseFloat(e.target.value));
                    setSelectedPreset('custom');
                  }}
                  className="w-full accent-[#FF6A2C] bg-[#ECECEC] h-1.5 rounded-lg appearance-none cursor-pointer"
                />
                <span className="text-[10px] text-[#6B6B6B] font-mono mt-1 block">Limit: &le; 1.05</span>
              </div>

              {/* Divergences */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label htmlFor="divergences-range" className="text-xs font-mono font-medium text-[#0A0A0A]">
                    Divergences (= 0)
                  </label>
                  <span className={`text-xs font-mono font-bold ${divergences === 0 ? 'text-emerald-600' : 'text-[#FF6A2C]'}`}>
                    {divergences}
                  </span>
                </div>
                <input
                  id="divergences-range"
                  type="range"
                  min="0"
                  max="30"
                  step="1"
                  value={divergences}
                  aria-label="MCMC divergent transitions"
                  aria-valuemin={0}
                  aria-valuemax={30}
                  aria-valuenow={divergences}
                  onChange={(e) => {
                    setDivergences(parseInt(e.target.value, 10));
                    setSelectedPreset('custom');
                  }}
                  className="w-full accent-[#FF6A2C] bg-[#ECECEC] h-1.5 rounded-lg appearance-none cursor-pointer"
                />
                <span className="text-[10px] text-[#6B6B6B] font-mono mt-1 block">Tolerance: 0</span>
              </div>

              {/* BFMI */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label htmlFor="bfmi-range" className="text-xs font-mono font-medium text-[#0A0A0A]">
                    Min BFMI (&ge; 0.20)
                  </label>
                  <span className={`text-xs font-mono font-bold ${bfmi >= 0.2 ? 'text-emerald-600' : 'text-[#FF6A2C]'}`}>
                    {bfmi.toFixed(2)}
                  </span>
                </div>
                <input
                  id="bfmi-range"
                  type="range"
                  min="0.05"
                  max="1.00"
                  step="0.01"
                  value={bfmi}
                  aria-label="Bayesian fraction of missing information"
                  aria-valuemin={0.05}
                  aria-valuemax={1.0}
                  aria-valuenow={bfmi}
                  onChange={(e) => {
                    setBfmi(parseFloat(e.target.value));
                    setSelectedPreset('custom');
                  }}
                  className="w-full accent-[#FF6A2C] bg-[#ECECEC] h-1.5 rounded-lg appearance-none cursor-pointer"
                />
                <span className="text-[10px] text-[#6B6B6B] font-mono mt-1 block">Minimum: &ge; 0.20</span>
              </div>
            </div>

            {/* Verdict Box */}
            <div className="p-6 rounded-xl bg-white border border-[#ECECEC] flex flex-col md:flex-row md:items-center justify-between gap-4 mb-4">
              <div>
                <div className="flex items-center space-x-2 mb-1.5">
                  <span className="text-xs font-mono text-[#6B6B6B] font-semibold">Server Gate Verdict:</span>
                  <span className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full border ${gateResult.badgeBg}`}>
                    {gateResult.verdict}
                  </span>
                </div>
                <p className="text-xs text-[#0A0A0A] font-medium">{gateResult.message}</p>
              </div>

              <div className="text-right">
                <span className="text-[11px] font-mono text-[#6B6B6B] block mb-1">Downstream Budget Status</span>
                <span
                  className={`text-xs font-mono font-bold px-3 py-1 rounded-xl inline-block border ${
                    gateResult.decisionAllowed
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : 'bg-[#FFF4ED] text-[#FF6A2C] border-[#FFE8D6]'
                  }`}
                >
                  {gateResult.decisionAllowed ? 'Optimization Unlocked' : 'Locked by Protocol'}
                </span>
              </div>
            </div>

            {/* Payload Preview */}
            <div className="p-4 rounded-xl bg-white border border-[#ECECEC] text-xs font-mono">
              <div className="text-[#6B6B6B] mb-2 font-medium">Downstream Execution Result:</div>
              {gateResult.decisionAllowed ? (
                <div className="text-emerald-700 space-y-1">
                  <div>✓ Authorization granted for organization: "org_enterprise_01"</div>
                  <div>✓ Optimal flighting: Search ($215k) · Social ($165k) · Video ($120k)</div>
                  <div>✓ Expected revenue: $2,184,000 (90% HDI: $1.94M to $2.42M)</div>
                </div>
              ) : (
                <div className="text-[#FF6A2C] space-y-1">
                  <div>✗ Protocol Exception: DECISION_GATE_BLOCKED</div>
                  <div>✗ Reason: Statistical diagnostics failed threshold check.</div>
                  <div>✗ Action: Downstream tool execution halted to prevent capital misallocation.</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* 7. BENTO STATS & ENGINE GRID (PREPILOT STYLE) */}
      <section id="engine" className="py-20 border-b border-[#ECECEC] bg-[#FAFAF7]">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <span className="text-xs font-mono uppercase tracking-wider text-[#FF6A2C] font-semibold">
              Platform Metrics
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0A0A0A] tracking-tight font-['Outfit'] mt-1">
              Production Statistics
            </h2>
            <p className="text-sm text-[#6B6B6B] mt-2">
              Verifiable proof behind every Bayesian model and decision gate.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Big Coral Card */}
            <div className="p-8 rounded-2xl bg-[#FF6A2C] text-white flex flex-col justify-between shadow-lg">
              <div>
                <div className="text-5xl font-extrabold font-mono mb-2">83+</div>
                <div className="text-sm font-bold uppercase tracking-wider opacity-90 font-['Outfit']">Contract Suites</div>
              </div>
              <p className="text-xs opacity-90 mt-6 leading-relaxed">
                Automated tests guarding schema drift, multi-tenant isolation, and diagnostic policies.
              </p>
            </div>

            {/* Stat Card 2 */}
            <div className="p-8 rounded-2xl bg-white border border-[#ECECEC] shadow-sm flex flex-col justify-between">
              <div>
                <div className="text-4xl font-extrabold text-[#0A0A0A] font-mono mb-2">12</div>
                <div className="text-xs font-bold uppercase tracking-wider text-[#6B6B6B] font-['Outfit']">Production Tools</div>
              </div>
              <p className="text-xs text-[#6B6B6B] mt-6 leading-relaxed">
                Exposed through standard MCP JSON-RPC for Claude Desktop, Cursor, and Gemini CLI.
              </p>
            </div>

            {/* Stat Card 3 */}
            <div className="p-8 rounded-2xl bg-white border border-[#ECECEC] shadow-sm flex flex-col justify-between">
              <div>
                <div className="text-4xl font-extrabold text-[#0A0A0A] font-mono mb-2">3</div>
                <div className="text-xs font-bold uppercase tracking-wider text-[#6B6B6B] font-['Outfit']">Diagnostic Gates</div>
              </div>
              <p className="text-xs text-[#6B6B6B] mt-6 leading-relaxed">
                Gelman-Rubin R-hat, zero divergences, and energy BFMI verified on every fit.
              </p>
            </div>

            {/* Stat Card 4 */}
            <div className="p-8 rounded-2xl bg-[#101828] text-white flex flex-col justify-between shadow-sm">
              <div>
                <div className="text-4xl font-extrabold font-mono text-[#00B8D9] mb-2">100%</div>
                <div className="text-xs font-bold uppercase tracking-wider text-zinc-400 font-['Outfit']">Bayesian Posterior</div>
              </div>
              <p className="text-xs text-zinc-400 mt-6 leading-relaxed">
                Zero heuristic point estimates. All channel returns carry highest density credible intervals.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 8. CAPABILITIES BENTO GRID (PREPILOT STYLE) */}
      <section id="capabilities" className="py-20 border-b border-[#ECECEC] bg-white">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mb-12">
            <span className="text-xs font-mono uppercase tracking-wider text-[#FF6A2C] font-semibold">
              Capabilities Surface
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0A0A0A] tracking-tight font-['Outfit'] mt-1">
              Choose the scientific workflow you need.
            </h2>
            <p className="text-sm text-[#6B6B6B] mt-2">
              PyMC Marketing MCP executes the right Bayesian engine and returns structured proof.
            </p>
          </div>

          {/* Category Tabs */}
          <div className="flex flex-wrap gap-2 mb-8">
            {[
              { id: 'mmm', label: 'Marketing Mix Modeling' },
              { id: 'decisions', label: 'Decision Science & Optimization' },
              { id: 'clv', label: 'Customer Lifetime Value' },
              { id: 'provenance', label: 'Provenance & Jobs' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveCategory(tab.id);
                  setSelectedToolIndex(0);
                }}
                className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
                  activeCategory === tab.id
                    ? 'bg-[#FF6A2C] text-white shadow-sm'
                    : 'bg-[#FAFAF7] text-[#6B6B6B] border border-[#ECECEC] hover:text-[#0A0A0A]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tool Inspector Card */}
          <div className="bg-[#FAFAF7] border border-[#ECECEC] rounded-2xl overflow-hidden shadow-md">
            <div className="grid grid-cols-1 md:grid-cols-3 border-b border-[#ECECEC] bg-white">
              {currentToolList.map((tool, idx) => (
                <button
                  key={tool.name}
                  onClick={() => setSelectedToolIndex(idx)}
                  className={`p-5 text-left border-b md:border-b-0 md:border-r border-[#ECECEC] last:border-r-0 transition-colors ${
                    selectedToolIndex === idx ? 'bg-[#FFF4ED] text-[#0A0A0A]' : 'hover:bg-[#FAFAF7] text-[#6B6B6B]'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs font-bold text-[#0A0A0A]">{tool.name}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white text-[#FF6A2C] border border-[#FFE8D6]">
                      {tool.badge}
                    </span>
                  </div>
                  <span className="text-[11px] text-[#6B6B6B] block truncate">{tool.tier}</span>
                </button>
              ))}
            </div>

            {currentTool && (
              <div className="p-8">
                <div className="mb-6">
                  <h4 className="text-base font-bold text-[#0A0A0A] font-['Outfit'] mb-1">{currentTool.name}</h4>
                  <p className="text-xs text-[#6B6B6B]">{currentTool.purpose}</p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 font-mono text-xs">
                  <div>
                    <div className="text-[11px] text-[#6B6B6B] mb-2 font-semibold flex items-center justify-between">
                      <span>Tool Invocation Payload</span>
                      <span>JSON-RPC</span>
                    </div>
                    <pre className="p-4 rounded-xl bg-white border border-[#ECECEC] text-[#0A0A0A] overflow-x-auto shadow-sm">
                      {currentTool.exampleCall}
                    </pre>
                  </div>

                  <div>
                    <div className="text-[11px] text-[#6B6B6B] mb-2 font-semibold flex items-center justify-between">
                      <span>Verified Schema Output</span>
                      <span className="text-emerald-600">Passed Gate</span>
                    </div>
                    <pre className="p-4 rounded-xl bg-white border border-[#ECECEC] text-emerald-800 overflow-x-auto shadow-sm">
                      {currentTool.exampleOutput}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 9. 1-CLICK MCP CONNECT (PREPILOT COPY BOXES) */}
      <section id="quickstart" className="py-20 border-b border-[#ECECEC] bg-[#FAFAF7]">
        <div className="max-w-[1240px] mx-auto px-4 sm:px-6">
          <div className="max-w-2xl mx-auto text-center mb-12">
            <span className="text-xs font-mono uppercase tracking-wider text-[#FF6A2C] font-semibold">
              Instant Setup
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0A0A0A] tracking-tight font-['Outfit'] mt-1">
              Start where you already work
            </h2>
            <p className="text-sm text-[#6B6B6B] mt-2">
              Connect PyMC Marketing MCP to Claude, Cursor, or Gemini in under sixty seconds.
            </p>
          </div>

          <div className="max-w-3xl mx-auto bg-white border border-[#ECECEC] rounded-2xl p-6 sm:p-8 shadow-md">
            {/* Copy boxes matching PrePilot */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
              <div>
                <span className="text-xs font-mono font-medium text-[#6B6B6B] block mb-2">Connector Name</span>
                <div
                  onClick={() => copySnippet('PyMC Marketing MCP', 'name')}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-[#FAFAF7] border border-[#ECECEC] hover:border-[#FF6A2C] cursor-pointer transition-colors"
                >
                  <span className="text-xs font-mono text-[#0A0A0A] font-semibold">PyMC Marketing MCP</span>
                  <button aria-label="Copy connector name" className="p-1 text-[#6B6B6B] hover:text-[#FF6A2C]">
                    {copiedConfig === 'name' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <span className="text-xs font-mono font-medium text-[#6B6B6B] block mb-2">Endpoint URL</span>
                <div
                  onClick={() => copySnippet('https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp', 'url')}
                  className="flex items-center justify-between p-3.5 rounded-xl bg-[#FAFAF7] border border-[#ECECEC] hover:border-[#FF6A2C] cursor-pointer transition-colors"
                >
                  <span className="text-xs font-mono text-[#0A0A0A] truncate mr-2">
                    https://pymc-marketing-mcp-uk3vf3u3eq-uc.a.run.app/mcp
                  </span>
                  <button aria-label="Copy endpoint URL" className="p-1 text-[#6B6B6B] hover:text-[#FF6A2C]">
                    {copiedConfig === 'url' ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
              </div>
            </div>

            {/* Client Tabs */}
            <div className="border-t border-[#ECECEC] pt-6">
              <div className="flex space-x-2 mb-4">
                <button
                  onClick={() => setActiveClientTab('claude')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
                    activeClientTab === 'claude'
                      ? 'bg-[#101828] text-white'
                      : 'bg-[#FAFAF7] text-[#6B6B6B] hover:text-[#0A0A0A]'
                  }`}
                >
                  Claude Desktop
                </button>
                <button
                  onClick={() => setActiveClientTab('cursor')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
                    activeClientTab === 'cursor'
                      ? 'bg-[#101828] text-white'
                      : 'bg-[#FAFAF7] text-[#6B6B6B] hover:text-[#0A0A0A]'
                  }`}
                >
                  Cursor IDE
                </button>
                <button
                  onClick={() => setActiveClientTab('gemini')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold font-mono transition-colors ${
                    activeClientTab === 'gemini'
                      ? 'bg-[#101828] text-white'
                      : 'bg-[#FAFAF7] text-[#6B6B6B] hover:text-[#0A0A0A]'
                  }`}
                >
                  Terminal / stdio
                </button>
              </div>

              <div className="p-4 rounded-xl bg-[#FAFAF7] border border-[#ECECEC] font-mono text-xs relative">
                <button
                  onClick={() => {
                    const text =
                      activeClientTab === 'claude'
                        ? claudeConfig
                        : activeClientTab === 'cursor'
                        ? cursorConfig
                        : geminiCommand;
                    copySnippet(text, activeClientTab);
                  }}
                  className="absolute top-3 right-3 flex items-center space-x-1 px-2.5 py-1 bg-white hover:bg-[#F3F3F0] text-[#0A0A0A] border border-[#ECECEC] rounded-lg text-[11px] font-semibold transition-colors shadow-sm"
                >
                  {copiedConfig === activeClientTab ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5 text-[#6B6B6B]" />
                      <span>Copy Config</span>
                    </>
                  )}
                </button>

                {activeClientTab === 'claude' && (
                  <div>
                    <span className="text-[#6B6B6B] block mb-2"># ~/Library/Application Support/Claude/claude_desktop_config.json</span>
                    <pre className="text-[#0A0A0A] overflow-x-auto leading-relaxed">{claudeConfig}</pre>
                  </div>
                )}

                {activeClientTab === 'cursor' && (
                  <div>
                    <span className="text-[#6B6B6B] block mb-2"># .cursor/mcp.json</span>
                    <pre className="text-[#0A0A0A] overflow-x-auto leading-relaxed">{cursorConfig}</pre>
                  </div>
                )}

                {activeClientTab === 'gemini' && (
                  <div>
                    <span className="text-[#6B6B6B] block mb-2"># Fast local stdio execution via uv:</span>
                    <pre className="text-[#FF6A2C] font-bold overflow-x-auto py-2 leading-relaxed">{geminiCommand}</pre>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 10. RADICAL CANDOR FAQ */}
      <section id="faq" className="py-20 border-b border-[#ECECEC] bg-white">
        <div className="max-w-3xl mx-auto px-4 sm:px-6">
          <div className="text-center mb-14">
            <span className="text-xs font-mono uppercase tracking-wider text-[#FF6A2C] font-semibold">
              Radical Candor
            </span>
            <h2 className="text-3xl sm:text-4xl font-extrabold text-[#0A0A0A] tracking-tight font-['Outfit'] mt-1">
              Frequently Answered Questions
            </h2>
            <p className="text-sm text-[#6B6B6B] mt-2">
              Honest answers regarding our decision-safety architecture and modeling boundaries.
            </p>
          </div>

          <div className="space-y-4">
            {FAQS.map((faq, i) => (
              <div key={i} className="p-6 rounded-2xl bg-[#FAFAF7] border border-[#ECECEC] shadow-sm">
                <h4 className="text-base font-bold text-[#0A0A0A] font-['Outfit'] mb-2">{faq.q}</h4>
                <p className="text-xs text-[#6B6B6B] leading-relaxed">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 11. FINAL HIGH-CONVERSION CTA */}
      <section className="py-24 bg-gradient-to-b from-[#FFF4ED] to-[#FAFAF7] border-b border-[#ECECEC]">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 text-center">
          <div className="w-14 h-14 rounded-2xl bg-white border border-[#FFE8D6] flex items-center justify-center mx-auto mb-6 shadow-md">
            <svg className="w-8 h-8" viewBox="0 0 32 32" fill="none" aria-hidden="true">
              <path d="M2 16 Q5 6 9 13 T16 13 T23 13 T30 13" stroke="#FF6A2C" strokeWidth="3.5" strokeLinecap="round" fill="none" />
              <path d="M2 22 Q5 12 9 19 T16 19 T23 19 T30 19" stroke="#FF6A2C" strokeWidth="3.5" strokeLinecap="round" fill="none" opacity="0.45" />
            </svg>
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold text-[#0A0A0A] tracking-tight mb-4 font-['Outfit']">
            Stop Guessing. Start Proving.
          </h2>
          <p className="text-base sm:text-lg text-[#6B6B6B] max-w-xl mx-auto mb-10 leading-relaxed font-normal">
            Mint your developer credentials, connect your AI agent in sixty seconds, and enforce decision safety on every marketing dollar.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button
              onClick={onOpenAuth}
              className="w-full sm:w-auto px-8 py-4 bg-[#FF6A2C] hover:bg-[#FF8A47] text-white font-semibold text-sm rounded-xl shadow-[0_4px_14px_rgba(255,106,44,0.35)] transition-all active:scale-[0.99]"
            >
              Get Free Developer Access
            </button>

            <a
              href="https://github.com/imMamdouhaboammar/pymc-marketing-mcp"
              target="_blank"
              rel="noreferrer"
              className="w-full sm:w-auto flex items-center justify-center space-x-2 px-7 py-4 bg-white hover:bg-[#FAFAF7] border border-[#ECECEC] text-[#0A0A0A] font-semibold text-sm rounded-xl transition-colors shadow-sm"
            >
              <span>View Source on GitHub</span>
              <ExternalLink className="w-4 h-4 text-[#6B6B6B]" />
            </a>
          </div>

          <div className="mt-10 text-xs font-mono text-[#6B6B6B]">
            Apache 2.0 Open Source · Free Local Mode · Streamable HTTP Cloud Run Ready
          </div>
        </div>
      </section>
    </div>
  );
};
