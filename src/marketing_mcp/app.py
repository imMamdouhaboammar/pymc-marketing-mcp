from __future__ import annotations

from .adapters.platform_client import PlatformClient
from .adapters.pymc_marketing import PyMCMarketingAdapter
from .config import Settings
from .credentials.service import CredentialService
from .jobs.executor import EnqueueOnlyJobExecutor
from .jobs.service import JobService
from .persistence import PersistenceBackend, build_persistence
from .services.clv_service import CLVService
from .services.dataset_service import DatasetService
from .services.decision_service import DecisionService
from .services.diagnostics_service import DiagnosticsService
from .services.insight_service import InsightService
from .services.modeling_service import ModelingService
from .services.plotting_service import PlottingService
from .skillpack.registry import get_runtime_registry
from .storage.artifacts import LocalArtifactStore


class Application:
    def __init__(
        self,
        settings: Settings | None = None,
        persistence: PersistenceBackend | None = None,
    ):
        self.settings = settings or Settings.from_env()
        self.persistence = persistence or build_persistence(self.settings)
        self.metadata = self.persistence.metadata
        self.artifacts = LocalArtifactStore(self.settings.artifact_dir)
        self.job_repo = self.persistence.jobs
        self.job_repo.recover_stale_running_jobs()
        job_executor = (
            EnqueueOnlyJobExecutor() if self.settings.job_execution_mode == "enqueue-only" else None
        )
        self.jobs = JobService(self.job_repo, executor=job_executor)
        self.credential_repo = self.persistence.credentials
        self.credentials = CredentialService(self.credential_repo)
        self.datasets = DatasetService(
            self.metadata, self.artifacts, self.settings.max_dataset_mb
        )
        self.models = ModelingService(
            self.metadata, self.artifacts, self.datasets, PyMCMarketingAdapter
        )
        self.diagnostics = DiagnosticsService(self.metadata, self.models)
        self.decisions = DecisionService(self.metadata, self.models)
        self.plots = PlottingService(self.artifacts, metadata=self.metadata)
        self.clv = CLVService(self.metadata, self.artifacts, datasets=self.datasets)
        self.insights = InsightService(self.metadata)
        self.skillpack = get_runtime_registry()
        self.platform_client = PlatformClient(self.settings)
