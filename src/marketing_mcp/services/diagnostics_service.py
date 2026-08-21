from __future__ import annotations
from marketing_mcp.domain.diagnostics.engine import diagnose_inferencedata

class DiagnosticsService:
    def __init__(self,metadata,modeling): self.metadata=metadata; self.modeling=modeling
    def diagnose(self,model_id):
        model,rec=self.modeling.load_model(model_id); result=diagnose_inferencedata(model.idata); result.model_id=model_id; rec.validation_state=result.decision_status; rec.diagnostics=result.model_dump(); self.metadata.put_model(rec.model_dump()); return result
