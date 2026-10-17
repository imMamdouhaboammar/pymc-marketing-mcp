import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronDown,
  Copy,
} from "lucide-react";
import { Tabs, TabList, Tab, TabPanel } from "react-aria-components/Tabs";
import { Button } from "react-aria-components/Button";
import { Disclosure, DisclosurePanel } from "react-aria-components/Disclosure";
import { Heading } from "react-aria-components/Heading";

const REPO = "https://github.com/imMamdouhaboammar/pymc-marketing-mcp";
const DOCS = `${REPO}/blob/main/docs`;

const ROLES = [
  {
    id: "marketer",
    name: "Digital Marketer",
    question: "Which channels should I examine before changing spend?",
    input:
      "Historical channel spend, business outcomes, dates, and relevant controls.",
    output:
      "Channel contribution estimates, uncertainty, and the limitations of the fitted model.",
    prompt:
      "List registered datasets and find the synthetic MMM sample. Check whether it is suitable for a marketing mix model. Explain what is missing before fitting anything. If a model is fitted, review diagnostics before suggesting a budget scenario.",
  },
  {
    id: "owner",
    name: "Business Owner",
    question: "What could a different budget allocation mean for the business?",
    input:
      "Suitable historical data, a planning period, and the budget limits you need to respect.",
    output:
      "A comparison with the model baseline, including uncertainty, assumptions, and spend limits.",
    prompt:
      "Find a fitted model from the local demo and review its decision status. If it permits decision support, ask for my budget scenario and compare it with the baseline. Explain the assumptions, uncertainty, and any extrapolation warnings. Keep my budget constraints explicit.",
  },
  {
    id: "ecommerce",
    name: "E-commerce Manager",
    question: "What might customers be worth beyond their first order?",
    input:
      "Suitable customer purchase history, transaction dates, and order values.",
    output:
      "Estimates of repeat purchases and customer lifetime value, with the model assumptions made clear.",
    prompt:
      "Check whether suitable customer transaction history is registered. The MMM sample is not CLV input. If transaction data is available, check its suitability for the supported purchase and monetary-value models. Explain the data requirements, then estimate customer lifetime value if the models are appropriate. Separate revenue estimates from profit.",
  },
  {
    id: "agency",
    name: "Agency Strategist",
    question: "How can I explain a budget recommendation to a client?",
    input:
      "Client-approved data, a specific planning question, and a fitted model with diagnostics.",
    output:
      "A scenario you can review with the client, alongside its evidence, caveats, and model references.",
    prompt:
      "Find the local demo model and review its diagnostics. If it permits decision support, ask for the client’s proposed spend scenario before comparing it with the baseline. Explain the evidence, assumptions, and uncertainty in plain English. Include the model and dataset references in the summary.",
  },
  {
    id: "analyst",
    name: "Marketing Analyst",
    question: "Can this fitted model support the proposed decision?",
    input: "A registered model and the decision you are considering.",
    output:
      "The actual diagnostic status, supporting evidence, and warnings that govern the next step.",
    prompt:
      "Find the local demo’s fitted MMM, if available. Diagnose it and explain its persisted decision status. If no fitted model exists, explain the missing prerequisite. Surface all warnings. If the model is rejected, keep decision-grade tools blocked and explain what evidence needs attention.",
  },
];

const COMMANDS = `git clone https://github.com/imMamdouhaboammar/pymc-marketing-mcp.git
cd pymc-marketing-mcp
uv sync --frozen --extra dev
uv run marketing-mcp-demo --fast`;

const LOCAL_CONFIG = JSON.stringify(
  {
    mcpServers: {
      "pymc-marketing": {
        command: "uv",
        args: [
          "run",
          "--directory",
          "/ABSOLUTE/PATH/TO/pymc-marketing-mcp",
          "marketing-mcp",
          "--transport",
          "stdio",
        ],
        env: {
          MARKETING_MCP_DATA_DIR: ".demo-runtime/data",
          MARKETING_MCP_INGEST_DIR: ".demo-runtime",
          MARKETING_MCP_ARTIFACT_DIR: ".demo-runtime/artifacts",
          MARKETING_MCP_METADATA_DB: ".demo-runtime/metadata.db",
        },
      },
    },
  },
  null,
  2,
);

const FAQS = [
  {
    q: "What data do I need?",
    a: "MMM starts with historical spend by channel, business outcomes, dates, and relevant controls. CLV uses customer transaction history. The sample supplies synthetic MMM data so you can explore without client data.",
  },
  {
    q: "Do I need to understand statistics?",
    a: "An AI assistant can help coordinate the workflow and explain results. Data preparation, modeling assumptions, and expert review still matter. Use an analyst’s judgment before acting on a model.",
  },
  {
    q: "Which AI client can I use?",
    a: "Use the local stdio configuration for Claude Desktop in the setup section. Other MCP clients may support the server’s transports, but their setup and access requirements differ. Check your client’s documentation before connecting.",
  },
  {
    q: "Does it change my live campaigns?",
    a: "You review recommendations and decide what to do. This MCP does not change live ad campaigns.",
  },
];

function CopyBlock({
  text,
  label,
  id,
}: {
  text: string;
  label: string;
  id?: string;
}) {
  const [state, setState] = useState<"idle" | "busy" | "copied" | "failed">(
    "idle",
  );
  const content = useRef<HTMLPreElement>(null);

  async function copy() {
    setState("busy");
    try {
      await navigator.clipboard.writeText(text);
      setState("copied");
    } catch {
      setState("failed");
      content.current?.focus();
    }
  }

  return (
    <div className="copy-block" id={id}>
      <div className="copy-toolbar">
        <span className="copy-status" role="status">
          {state === "copied" && "Copied"}
          {state === "busy" && "Copying…"}
          {state === "failed" && "Select the text below and copy it manually."}
        </span>
        <button
          type="button"
          onClick={copy}
          disabled={state === "busy"}
          className="copy-button"
          aria-label={label}
        >
          {state === "copied" ? (
            <Check size={15} aria-hidden="true" />
          ) : (
            <Copy size={15} aria-hidden="true" />
          )}
          <span>{label}</span>
        </button>
      </div>
      <pre
        className="copy-text"
        ref={content}
        tabIndex={0}
        aria-label={label.replace("Copy ", "")}
      >
        {text}
      </pre>
    </div>
  );
}

function Fold({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Disclosure className="teaser-disclosure">
      <Heading level={3}>
        <Button slot="trigger" className="disclosure-trigger">
          <span>{title}</span>
          <ChevronDown size={18} aria-hidden="true" />
        </Button>
      </Heading>
      <DisclosurePanel className="disclosure-panel">{children}</DisclosurePanel>
    </Disclosure>
  );
}

export function TeaserLandingPage() {
  const [roleId, setRoleId] = useState("marketer");
  const [narrow, setNarrow] = useState(
    () => window.matchMedia("(max-width: 759px)").matches,
  );
  const role = ROLES.find((item) => item.id === roleId) ?? ROLES[0];

  useEffect(() => {
    const query = window.matchMedia("(max-width: 759px)");
    const update = () => setNarrow(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return (
    <>
      <section className="teaser-hero" aria-labelledby="hero-title">
        <div className="teaser-container">
          <h1 id="hero-title">
            Put evidence behind
            <br className="desktop-break" /> your next marketing{" "}
            <span>decision.</span>
          </h1>
          <p className="hero-description">
            Use a compatible AI assistant to model marketing performance,
            compare budget scenarios, and estimate customer value with
            PyMC-Marketing. Review the evidence and uncertainty before you act.
          </p>
          <div className="hero-actions">
            <a className="teaser-primary" href="#quickstart">
              Try the sample workflow{" "}
              <ArrowRight size={18} aria-hidden="true" />
            </a>
            <a className="teaser-text-link" href="#your-work">
              See what you can ask <ArrowDown size={16} aria-hidden="true" />
            </a>
          </div>
          <p className="hero-context">
            Open source <span aria-hidden="true">·</span> Start with synthetic
            data
          </p>

          <article className="decision-brief" aria-labelledby="brief-title">
            <div className="brief-topline">
              <span>A question worth testing</span>
              <span>Illustrative workflow</span>
            </div>
            <div className="brief-content">
              <div className="brief-question">
                <h2 id="brief-title">
                  What could happen if we moved budget between channels?
                </h2>
                <p>Turn a planning question into a scenario you can examine.</p>
                <span className="brief-footnote">
                  Example only. No model has been run here.
                </span>
              </div>
              <dl className="brief-evidence">
                <div>
                  <dt>Start with</dt>
                  <dd>Prepared historical data and a fitted model</dd>
                </div>
                <div>
                  <dt>Compare</dt>
                  <dd>
                    Scenario estimates against the baseline, with uncertainty
                  </dd>
                </div>
                <div>
                  <dt>Check before acting</dt>
                  <dd>Diagnostics, assumptions, and extrapolation warnings</dd>
                </div>
              </dl>
            </div>
          </article>
        </div>
      </section>

      <section
        className="teaser-section science-section"
        id="how-it-works"
        aria-labelledby="science-title"
      >
        <div className="teaser-container">
          <h2 id="science-title" className="section-title">
            The science behind it.
            <br />
            The connection to your workflow.
          </h2>
          <div className="science-columns">
            <div>
              <h3>PyMC-Marketing</h3>
              <p>
                The open-source Python library for Bayesian marketing analysis,
                including marketing mix modeling and customer lifetime value.
              </p>
              <a
                className="teaser-text-link"
                href="https://www.pymc-marketing.io/en/stable/"
                target="_blank"
                rel="noreferrer"
              >
                Explore the library{" "}
                <ArrowUpRight size={16} aria-hidden="true" />
              </a>
            </div>
            <div>
              <h3>PyMC Marketing MCP</h3>
              <p>
                The interface that lets compatible AI agents use supported
                modeling workflows, validate data, and retrieve evidence. The
                statistical libraries perform the calculations.
              </p>
              <a
                className="teaser-text-link"
                href={`${DOCS}/CAPABILITIES.md`}
                target="_blank"
                rel="noreferrer"
              >
                See supported workflows{" "}
                <ArrowUpRight size={16} aria-hidden="true" />
              </a>
            </div>
          </div>
          <ol className="workflow-sequence" aria-label="Analysis workflow">
            {[
              "Business question",
              "Prepared data",
              "Statistical model",
              "Evidence review",
            ].map((step, index) => (
              <li key={step}>
                <span>{step}</span>
                {index < 3 && <ArrowRight size={16} aria-hidden="true" />}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section
        className="teaser-section roles-section"
        id="your-work"
        aria-labelledby="roles-title"
      >
        <div className="teaser-container">
          <h2 id="roles-title" className="section-title" tabIndex={-1}>
            Start with a decision
            <br />
            you already need to make.
          </h2>
          <Tabs
            className="role-tabs"
            orientation={narrow ? "horizontal" : "vertical"}
            selectedKey={roleId}
            onSelectionChange={(key) => setRoleId(String(key))}
          >
            <TabList aria-label="Your role" className="role-list">
              {ROLES.map((item) => (
                <Tab key={item.id} id={item.id} className="role-tab">
                  {item.name}
                  <ArrowUpRight size={16} aria-hidden="true" />
                </Tab>
              ))}
            </TabList>
            {ROLES.map((item) => (
              <TabPanel key={item.id} id={item.id} className="role-panel">
                <h3>{item.question}</h3>
                <dl className="role-context">
                  <div>
                    <dt>What you bring</dt>
                    <dd>{item.input}</dd>
                  </div>
                  <div>
                    <dt>What you can review</dt>
                    <dd>{item.output}</dd>
                  </div>
                </dl>
                <div className="role-prompt">
                  <p>Ask your connected assistant</p>
                  <CopyBlock text={item.prompt} label="Copy first prompt" />
                </div>
                <a className="teaser-text-link" href="#quickstart">
                  Try this as a {item.name}{" "}
                  <ArrowRight size={16} aria-hidden="true" />
                </a>
              </TabPanel>
            ))}
          </Tabs>
        </div>
      </section>

      <section
        className="teaser-section evidence-section"
        aria-labelledby="evidence-title"
      >
        <div className="teaser-container evidence-layout">
          <div>
            <h2 id="evidence-title" className="section-title">
              Review the evidence
              <br />
              before changing the plan.
            </h2>
            <p>
              Results depend on the data, assumptions, and model quality.
              Sometimes the useful next step is better data.
            </p>
          </div>
          <div className="evidence-notes">
            <p>
              <strong>Statistical calculations.</strong> Supported model outputs
              come from PyMC-Marketing, PyMC, and ArviZ.
            </p>
            <p>
              <strong>Diagnostic conditions.</strong> Defined decision-grade
              operations require an approved model status. Cautions stay
              visible; approval does not establish causal certainty.
            </p>
            <p>
              <strong>Evidence to revisit.</strong> Inspect the model, dataset
              references, diagnostics, and warnings behind a result.
            </p>
            <a
              className="teaser-text-link"
              href={`${DOCS}/DECISION-INTEGRITY.md`}
              target="_blank"
              rel="noreferrer"
            >
              Read the decision policy{" "}
              <ArrowUpRight size={16} aria-hidden="true" />
            </a>
          </div>
          <p className="beta-note">
            <strong>Advanced beta</strong>
            <span>
              Not release-approved. Review{" "}
              <a
                href={`${DOCS}/PRODUCTION-READINESS.md`}
                target="_blank"
                rel="noreferrer"
              >
                current limitations
              </a>{" "}
              before real use.
            </span>
          </p>
        </div>
      </section>

      <section
        className="teaser-section setup-section"
        id="quickstart"
        aria-labelledby="setup-title"
      >
        <div className="teaser-container">
          <div className="setup-heading">
            <h2 id="setup-title" className="section-title" tabIndex={-1}>
              Try one question before
              <br />
              using your own data.
            </h2>
            <p>
              Start locally with Python 3.12 or 3.13 and{" "}
              <a
                href="https://docs.astral.sh/uv/getting-started/installation/"
                target="_blank"
                rel="noreferrer"
              >
                uv
              </a>
              . An analyst can help with setup.
            </p>
          </div>
          <ol className="setup-steps">
            <li>
              <div className="step-description">
                <h3>Run the synthetic example</h3>
                <p>
                  Register data, fit an MMM, and inspect diagnostics. This
                  reduced-sampling smoke demo may return cautions or stop at the
                  decision gate.
                </p>
              </div>
              <div>
                <CopyBlock
                  id="sample-commands"
                  text={COMMANDS}
                  label="Copy commands"
                />
                <p className="setup-note">
                  This runs in your terminal, not a chat window. Sampling takes
                  time.{" "}
                  <a
                    href={`${REPO}#quick-start`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Full setup guide
                  </a>
                </p>
              </div>
            </li>
            <li>
              <div className="step-description">
                <h3>Connect a supported AI client</h3>
                <p>
                  For a local conversation, use Claude Desktop with the server’s
                  stdio transport.
                </p>
              </div>
              <Fold title="Claude Desktop: local connection">
                <p>
                  In Claude Desktop, open Settings → Developer → Edit Config.
                  Merge this entry into <code>mcpServers</code>. Replace the
                  absolute path, save, and restart Claude Desktop. The{" "}
                  <code>uv</code> command must be available to the app. Storage
                  paths resolve inside the project directory, sharing the CLI
                  demo’s datasets and models.
                </p>
                <CopyBlock
                  id="local-client-config"
                  text={LOCAL_CONFIG}
                  label="Copy configuration"
                />
                <a
                  className="teaser-text-link"
                  href="https://modelcontextprotocol.io/docs/develop/connect-local-servers"
                  target="_blank"
                  rel="noreferrer"
                >
                  Official local connection guide{" "}
                  <ArrowUpRight size={16} aria-hidden="true" />
                </a>
              </Fold>
            </li>
            <li id="first-question">
              <div className="step-description">
                <h3>Ask your first question</h3>
                <p>
                  For your work as a <strong>{role.name}</strong>. Ask the
                  assistant to list datasets and identify the sample model, if
                  fitting completed. CLV needs customer transaction history,
                  which this MMM sample does not provide.
                </p>
              </div>
              <CopyBlock
                key={role.id}
                text={role.prompt}
                label="Copy selected prompt"
              />
            </li>
          </ol>
          <p className="setup-boundary">
            <strong>Advanced beta.</strong> Explore with synthetic data first.
            Review your AI client’s data handling and the{" "}
            <a href={`${DOCS}/SECURITY.md`} target="_blank" rel="noreferrer">
              deployment security guidance
            </a>{" "}
            before using business data.
          </p>
        </div>
      </section>

      <section
        className="teaser-section faq-section"
        id="faq"
        aria-labelledby="faq-title"
      >
        <div className="teaser-container">
          <div className="faq-layout">
            <h2 id="faq-title" className="section-title">
              A few things
              <br />
              to know first.
            </h2>
            <div>
              {FAQS.map((faq) => (
                <Fold key={faq.q} title={faq.q}>
                  <p>{faq.a}</p>
                </Fold>
              ))}
            </div>
          </div>
          <div className="teaser-close">
            <h2>
              Start with a sample.
              <br />
              Then bring your own question.
            </h2>
            <a href="#quickstart" className="teaser-primary">
              Try the sample workflow{" "}
              <ArrowRight size={18} aria-hidden="true" />
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
