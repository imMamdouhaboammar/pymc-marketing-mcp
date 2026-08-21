from __future__ import annotations
from pathlib import Path
from marketing_mcp.app import Application
from marketing_mcp.schemas.models import FitMMMInput,BudgetOptimizationInput,BudgetSimulationInput,ToolEnvelope
from marketing_mcp.errors import DomainError
from marketing_mcp.security import safe_ingest_path

def _env(summary=None,evidence=None,warnings=None,provenance=None,next_actions=None):
    return ToolEnvelope(summary=summary or {},evidence=evidence or {},warnings=warnings or [],provenance=provenance or {},next_actions=next_actions or []).model_dump()

def create_server(app:Application|None=None):
    try:
        from mcp.server import MCPServer
    except ImportError as e:
        raise RuntimeError("Install project dependencies to run the MCP server") from e
    app=app or Application(); mcp=MCPServer("PyMC Marketing MCP",instructions="Use this server for statistical marketing calculations. Never invent model outputs. Diagnose fitted MMMs before budget decisions.")
    def guarded(fn):
        async def wrapper(*args,**kwargs):
            try: return fn(*args,**kwargs)
            except DomainError as e: return e.to_dict()
        return wrapper
    @mcp.tool(name="register_dataset",description="Register a local CSV or Parquet marketing dataset and return a stable dataset reference.")
    async def register_dataset(path:str):
        try:
            source=safe_ingest_path(Path(path),app.settings.ingest_dir,app.settings.max_dataset_mb*1024*1024); r=app.datasets.register_file(source); return _env(summary=r.model_dump(),provenance={"fingerprint":r.fingerprint},next_actions=["inspect_dataset","validate_dataset"])
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="inspect_dataset",description="Inspect a registered dataset before MMM configuration. Returns candidate targets, channels, controls, frequency and data issues.")
    async def inspect_dataset(dataset_id:str):
        try:
            r=app.datasets.inspect(dataset_id); return _env(summary=r.model_dump(),warnings=[x.model_dump() for x in r.issues],next_actions=["validate_dataset"] if r.mmm_candidate else ["repair_dataset"])
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="validate_dataset",description="Run MMM-specific data quality, panel-shape and identifiability checks. This must pass before fitting.")
    async def validate_dataset(dataset_id:str,date_column:str,target_column:str,channel_columns:list[str],control_columns:list[str]|None=None,dims:list[str]|None=None):
        try:
            r=app.datasets.validate(dataset_id,date_column,target_column,channel_columns,control_columns or [],dims or []); return _env(summary={"dataset_id":dataset_id,"valid_for_modeling":r.valid_for_modeling},evidence={"findings":[f.model_dump() for f in r.findings]},next_actions=["fit_mmm"] if r.valid_for_modeling else ["repair_dataset"])
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="fit_mmm",description="Fit a real Bayesian Marketing Mix Model with PyMC-Marketing using typed, controlled configuration. No arbitrary Python is accepted.")
    async def fit_mmm(config:dict):
        try:
            r=app.models.fit(FitMMMInput(**config)); return _env(summary=r.model_dump(),provenance=r.config.get("provenance",{}),next_actions=["diagnose_mmm"])
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="get_model_status",description="Get persisted model fit state and safe failure information.")
    async def get_model_status(model_id:str):
        try: return _env(summary=app.models.status(model_id).model_dump())
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="diagnose_mmm",description="Mandatory diagnostic gate. Checks sampler health plus posterior predictive coverage, predictive error and residual behavior before decision tools may run.")
    async def diagnose_mmm(model_id:str):
        try:
            r=app.diagnostics.diagnose(model_id); return _env(summary={"model_id":model_id,"decision_status":r.decision_status,"decision_tools_enabled":r.decision_tools_enabled},evidence=r.diagnostics,warnings=[w.model_dump() for w in r.warnings],next_actions=["get_channel_contributions","get_incremental_roas","get_response_curves"] + (["simulate_budget","optimize_budget"] if r.decision_tools_enabled else ["refit_model"]))
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="get_channel_contributions",description="Return posterior channel contribution summaries from the fitted PyMC-Marketing model. Does not fabricate estimates.")
    async def get_channel_contributions(model_id:str):
        try:
            r=app.decisions.contributions(model_id); return _env(summary={"model_id":model_id,"channels":r["channels"]},evidence={"variable":r["variable"]},provenance=r["provenance"])
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="get_incremental_roas",description="Return total and marginal iROAS from PyMC-Marketing's official incrementality API, including posterior uncertainty. No ad-hoc LLM ROAS calculation.")
    async def get_incremental_roas(model_id:str):
        try:
            r=app.decisions.iroas(model_id); return _env(summary=r,provenance=r.get("provenance",{}))
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="get_response_curves",description="Return response/saturation information sampled by PyMC-Marketing rather than raw posterior arrays.")
    async def get_response_curves(model_id:str):
        try:
            r=app.decisions.response_curves(model_id); return _env(summary=r,provenance=r.get("provenance",{}))
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="simulate_budget",description="Evaluate the exact requested channel or dimension-cell scenario with posterior response sampling. Rejected models are blocked.")
    async def simulate_budget(config:dict):
        try:
            r=app.decisions.simulate(BudgetSimulationInput(**config)); return _env(summary=r,evidence={"caveats":r.get("caveats",[])},provenance=r.get("provenance",{}))
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="optimize_budget",description="Use PyMC-Marketing budget optimization under channel or dimension-cell constraints, then compare baseline and recommended posterior responses. Requires a diagnosed model.")
    async def optimize_budget(config:dict):
        try:
            r=app.decisions.optimize(BudgetOptimizationInput(**config)); return _env(summary=r,provenance=r.get("provenance",{}))
        except DomainError as e: return e.to_dict()
    @mcp.tool(name="recommend_next_measurement",description="Recommend evidence-gathering options when model/data signals imply material uncertainty. It can explicitly return that no single experiment is implied.")
    async def recommend_next_measurement(model_id:str):
        try: return _env(summary=app.decisions.recommend_measurement(model_id))
        except DomainError as e: return e.to_dict()
    @mcp.resource("marketing://datasets/{dataset_id}")
    async def dataset_resource(dataset_id:str)->str:
        import json; return json.dumps(app.metadata.get_dataset(dataset_id),indent=2)
    @mcp.resource("marketing://models/{model_id}")
    async def model_resource(model_id:str)->str:
        import json; return json.dumps(app.metadata.get_model(model_id),indent=2)
    @mcp.resource("marketing://models/{model_id}/diagnostics")
    async def diagnostics_resource(model_id:str)->str:
        import json; return json.dumps(app.metadata.get_model(model_id).get("diagnostics"),indent=2)
    return mcp
