from __future__ import annotations
import platform, uuid
from datetime import datetime, timezone
from marketing_mcp.errors import DomainError
from marketing_mcp.schemas.models import FitMMMInput,ModelRecord

def _utc(): return datetime.now(timezone.utc).isoformat()

class ModelingService:
    def __init__(self,metadata,artifacts,datasets,adapter_factory): self.metadata=metadata; self.artifacts=artifacts; self.datasets=datasets; self.adapter_factory=adapter_factory
    def fit(self,input:FitMMMInput)->ModelRecord:
        validation=self.datasets.validate(input.dataset_id,input.date_column,input.target_column,input.channel_columns,input.control_columns,input.dims)
        if not validation.valid_for_modeling: raise DomainError("INVALID_DATASET","Dataset failed MMM validation",evidence={"findings":[f.model_dump() for f in validation.findings]},next_action="Fix dataset errors before fitting")
        now=_utc(); model_id=f"mmm_{uuid.uuid4().hex[:12]}"; config=input.model_dump(); rec=ModelRecord(model_id=model_id,dataset_id=input.dataset_id,status="running",config=config,created_at=now,updated_at=now); self.metadata.put_model(rec.model_dump())
        try:
            adapter=self.adapter_factory(); path=self.artifacts.model_path(model_id); adapter.fit(self.datasets.load(input.dataset_id),config,path); rec.status="completed"; rec.artifact_path=str(path); rec.updated_at=_utc(); rec.config["provenance"]={"python":platform.python_version(),**adapter.versions()}
        except DomainError as e:
            rec.status="failed"; rec.failure=e.to_dict()["error"]; rec.updated_at=_utc(); self.metadata.put_model(rec.model_dump()); raise
        except Exception as e:
            rec.status="failed"; rec.failure={"code":"MODEL_FIT_FAILED","message":str(e)[:1000],"type":type(e).__name__}; rec.updated_at=_utc(); self.metadata.put_model(rec.model_dump()); raise DomainError("MODEL_FIT_FAILED","PyMC-Marketing model fitting failed",evidence=rec.failure) from e
        self.metadata.put_model(rec.model_dump()); return rec
    def status(self,model_id): return ModelRecord(**self.metadata.get_model(model_id))
    def load_model(self,model_id):
        rec=self.status(model_id)
        if rec.status!="completed": raise DomainError("MODEL_NOT_FITTED","Model fitting has not completed",evidence={"status":rec.status})
        return self.adapter_factory().load(self.artifacts.require(model_id)), rec
