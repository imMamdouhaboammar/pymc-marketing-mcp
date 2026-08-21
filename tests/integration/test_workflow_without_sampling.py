import pandas as pd
from marketing_mcp.app import Application
from marketing_mcp.config import Settings

def test_dataset_workflow_persists(tmp_path):
    settings=Settings(data_dir=tmp_path/"data", artifact_dir=tmp_path/"artifacts", metadata_db=tmp_path/"meta.db", max_dataset_mb=10)
    app=Application(settings)
    f=tmp_path/"mmm.csv"
    pd.DataFrame({"date":pd.date_range("2025-01-06",periods=80,freq="W-MON"),"revenue":range(80),"meta":range(80),"google":[x%17 for x in range(80)]}).to_csv(f,index=False)
    reg=app.datasets.register_file(f)
    assert app.datasets.inspect(reg.dataset_id).mmm_candidate
    validation=app.datasets.validate(reg.dataset_id,"date","revenue",["meta","google"],[])
    assert validation.dataset_id==reg.dataset_id
