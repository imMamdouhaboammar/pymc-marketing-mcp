"""Low-cardinality operational metrics collector (Wave 6 Task 2)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class MetricsCollector:
    """In-memory low-cardinality Prometheus-compatible metric registry."""

    _lock: Lock = field(default_factory=Lock)
    counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    histograms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    gauges: dict[str, float] = field(default_factory=lambda: defaultdict(float))

    def increment_counter(self, name: str, value: int = 1, labels: dict[str, str] | None = None) -> None:
        key = self._format_key(name, labels)
        with self._lock:
            self.counters[key] += value

    def observe_duration(self, name: str, duration_seconds: float, labels: dict[str, str] | None = None) -> None:
        key = self._format_key(name, labels)
        with self._lock:
            self.histograms[key].append(duration_seconds)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._format_key(name, labels)
        with self._lock:
            self.gauges[key] = value

    def get_metrics_snapshot(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms_count": {k: len(v) for k, v in self.histograms.items()},
            }

    def _format_key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        formatted_labels = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{formatted_labels}}}"


GLOBAL_METRICS = MetricsCollector()
