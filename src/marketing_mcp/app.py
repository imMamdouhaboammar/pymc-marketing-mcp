from __future__ import annotations
from .config import Settings
from .storage.metadata import SQLiteMetadataStore
from .storage.artifacts import LocalArtifactStore
from .services.dataset_service import DatasetService
from .services.modeling_service import ModelingService
from .services.diagnostics_service import DiagnosticsService
from .services.decision_service import DecisionService
from .adapters.pymc_marketing import PyMCMarketingAdapter

class Application:
    def __init__(self,settings:Settings|None=None):
        self.settings=settings or Settings.from_env(); self.metadata=SQLiteMetadataStore(self.settings.metadata_db); self.artifacts=LocalArtifactStore(self.settings.artifact_dir); self.datasets=DatasetService(self.metadata,self.settings.data_dir,self.settings.max_dataset_mb); self.models=ModelingService(self.metadata,self.artifacts,self.datasets,PyMCMarketingAdapter); self.diagnostics=DiagnosticsService(self.metadata,self.models); self.decisions=DecisionService(self.metadata,self.models)
