from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models import ChatRequest, ChatResponse
from app.services.ask_metrics_provider import AskMetricsProvider, MetricResult
from app.services.excel_ask_metrics_provider import ExcelAskMetricsProvider


class AskMetricsService:
    """Route local ask-metrics queries to configured read-only providers."""

    def __init__(
        self,
        data_dir: str | Path,
        config_path: str | Path | None = None,
        *,
        providers: list[AskMetricsProvider] | None = None,
    ) -> None:
        self.providers = providers or [ExcelAskMetricsProvider(data_dir, config_path)]

    def respond(self, request: ChatRequest, *, message_id: str | None = None) -> ChatResponse | None:
        result = self.query(request.text)
        if result is None:
            return None
        return _to_chat_response(request, result, message_id=message_id)

    def query(self, text: str) -> MetricResult | None:
        for provider in self.providers:
            result = provider.query(text)
            if result is not None:
                return result
        return None


def _to_chat_response(
    request: ChatRequest,
    result: MetricResult,
    *,
    message_id: str | None = None,
) -> ChatResponse:
    return ChatResponse(
        session_id=request.session_id,
        message_id=message_id or f"msg-{uuid4().hex[:12]}",
        type="answer",
        title=result.title,
        speak_text=result.speak_text,
        display={
            "mode": "text",
            "summary": result.summary,
            "bullets": [*result.bullets, f"数据来源：{result.source}"],
            "source": result.source,
        },
    )
