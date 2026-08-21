from __future__ import annotations
import argparse, json, tempfile
from pathlib import Path
from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_mmm
from marketing_mcp.schemas.models import FitMMMInput,BudgetSimulationInput,BudgetOptimizationInput

def main():
    p=argparse.ArgumentParser(); p.add_argument("--fast",action="store_true",help="Use fewer posterior draws for a local smoke demo"); args=p.parse_args(); work=Path(".demo-runtime"); work.mkdir(exist_ok=True); csv=work/"synthetic_mmm.csv"; generate_synthetic_mmm().to_csv(csv,index=False); app=Application(Settings(data_dir=work/"data",artifact_dir=work/"artifacts",metadata_db=work/"metadata.db")); reg=app.datasets.register_file(csv); print("1 register",reg.model_dump()); print("2 inspect",app.datasets.inspect(reg.dataset_id).model_dump()); val=app.datasets.validate(reg.dataset_id,"date","revenue",["meta","google","tiktok","youtube"],["discount"]); print("3 validate",val.valid_for_modeling)
    cfg=FitMMMInput(dataset_id=reg.dataset_id,date_column="date",target_column="revenue",channel_columns=["meta","google","tiktok","youtube"],control_columns=["discount"],yearly_seasonality=2,sampler={"draws":300 if args.fast else 1000,"tune":300 if args.fast else 1000,"chains":2 if args.fast else 4,"target_accept":0.9,"random_seed":42}); model=app.models.fit(cfg); print("4 fit",model.model_id); diag=app.diagnostics.diagnose(model.model_id); print("5 diagnose",diag.model_dump()); print("6 contributions",json.dumps(app.decisions.contributions(model.model_id),indent=2));
    try: print("7 iroas",json.dumps(app.decisions.iroas(model.model_id),indent=2))
    except Exception as e: print("7 iroas unavailable",e)
    print("8 simulate",json.dumps(app.decisions.simulate(BudgetSimulationInput(model_id=model.model_id,planning_periods=8,changes={"meta":{"type":"relative","value":-0.20},"google":{"type":"relative","value":0.15}})),indent=2)); print("9 optimize",json.dumps(app.decisions.optimize(BudgetOptimizationInput(model_id=model.model_id,budget=2_500_000,planning_periods=8)),indent=2)); print("10 communicate median + 94% interval + diagnostics + caveats + provenance; never present posterior estimates as deterministic facts")
if __name__=="__main__": main()
