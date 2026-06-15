from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MetricResult:
    title: str
    speak_text: str
    summary: str
    bullets: list[str]
    source: str
    provider: str = "excel"
    metric_id: str | None = None


@dataclass(frozen=True)
class AskMetricsProviderStatus:
    name: str
    status: str
    source: str = "code_default"
    notes: str = ""


class AskMetricsProvider(Protocol):
    name: str

    def query(self, text: str) -> MetricResult | None:
        ...

    def status(self) -> AskMetricsProviderStatus:
        ...


class DatabaseAskMetricsProvider:
    name = "database"

    def query(self, text: str) -> MetricResult | None:
        return None

    def status(self) -> AskMetricsProviderStatus:
        return AskMetricsProviderStatus(
            name=self.name,
            status="not_implemented",
            notes="Reserved for stage 3+ read-only table/view metrics. This stub never opens a database connection or executes SQL.",
        )
