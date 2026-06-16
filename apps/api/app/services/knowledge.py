from __future__ import annotations

from uuid import uuid4

from app.config import Settings
from app.models import ChatRequest, ChatResponse, ErrorDetail
from app.services.knowledge_provider import (
    DEFAULT_KNOWLEDGE_FALLBACK_TEXT,
    KnowledgeDirectProvider,
    KnowledgeProviderError,
    KnowledgeResult,
    RagflowKnowledgeRetriever,
    SourceBoundSummarizer,
)


class KnowledgeService:
    """Route knowledge questions to the configured source-bound provider."""

    def __init__(self, provider: KnowledgeDirectProvider, *, mode: str) -> None:
        self.provider = provider
        self.mode = _normalize_mode(mode)

    def respond(self, request: ChatRequest, *, message_id: str | None = None) -> ChatResponse | None:
        if self.mode == "dora":
            return None
        try:
            result = self.provider.query(request.text)
        except KnowledgeProviderError:
            if self.mode == "auto":
                return None
            raise
        if result is None:
            return None
        return _to_chat_response(request, result, message_id=message_id)


def build_knowledge_service(settings: Settings) -> KnowledgeService:
    mode = _normalize_mode(settings.knowledge_mode)
    retriever = RagflowKnowledgeRetriever(
        base_url=settings.ragflow_base_url,
        mcp_url=settings.ragflow_mcp_url,
        api_key=settings.ragflow_api_key,
        transport=settings.knowledge_retrieval_transport,
        dataset_ids=_split_csv(settings.knowledge_dataset_ids),
        dataset_name=settings.knowledge_dataset_name,
        page_size=settings.knowledge_page_size,
        top_k=settings.knowledge_top_k,
        similarity_threshold=settings.knowledge_similarity_threshold,
        max_chunk_chars=settings.knowledge_max_chunk_chars,
        timeout_seconds=settings.knowledge_timeout_seconds,
    )
    summarizer = SourceBoundSummarizer(
        require_sources=settings.knowledge_require_sources,
        fallback_text=settings.knowledge_fallback_text or DEFAULT_KNOWLEDGE_FALLBACK_TEXT,
        max_answer_chars=settings.knowledge_max_answer_chars,
    )
    provider = KnowledgeDirectProvider(
        retriever=retriever,
        summarizer=summarizer,
        enabled=mode in {"local_ragflow_llm", "auto"},
        fallback_text=settings.knowledge_fallback_text or DEFAULT_KNOWLEDGE_FALLBACK_TEXT,
    )
    return KnowledgeService(provider, mode=mode)


def _to_chat_response(
    request: ChatRequest,
    result: KnowledgeResult,
    *,
    message_id: str | None = None,
) -> ChatResponse:
    response_message_id = message_id or f"msg-{uuid4().hex[:12]}"
    if result.result_type == "fallback":
        code = result.error_code or "KNOWLEDGE_NO_EVIDENCE"
        return ChatResponse(
            session_id=request.session_id,
            message_id=response_message_id,
            type="fallback",
            speak_text=result.speak_text,
            reason=result.reason or code,
            error=ErrorDetail(code=code, message=result.speak_text),
        )

    sources = [source.as_dict() for source in result.sources]
    bullets = list(result.bullets)
    if result.source_summary:
        bullets.append(f"来源：{result.source_summary}")
    return ChatResponse(
        session_id=request.session_id,
        message_id=response_message_id,
        type="answer",
        title=result.title,
        speak_text=result.speak_text,
        display={
            "mode": "text",
            "summary": result.summary or result.speak_text,
            "bullets": bullets,
            "sources": sources,
            "source_summary": result.source_summary,
            "source": result.source_summary,
            "audit": {
                "capability": "knowledge",
                "provider": result.provider,
                "require_sources": True,
                "no_evidence_policy": "fallback",
            },
        },
    )


def _normalize_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"local", "local_ragflow", "local_ragflow_llm", "knowledge_direct"}:
        return "local_ragflow_llm"
    if mode == "auto":
        return "auto"
    return "dora"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def knowledge_error_response(
    request: ChatRequest,
    *,
    message_id: str | None = None,
    exc: KnowledgeProviderError,
) -> ChatResponse:
    return ChatResponse(
        session_id=request.session_id,
        message_id=message_id or f"msg-{uuid4().hex[:12]}",
        type="fallback",
        speak_text=exc.user_message,
        reason=exc.code,
        error=ErrorDetail(code=exc.code, message=exc.user_message),
    )
