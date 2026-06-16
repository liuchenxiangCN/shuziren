from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx


DEFAULT_KNOWLEDGE_FALLBACK_TEXT = "知识库未找到可靠依据，请补充资料后再试。"


@dataclass(frozen=True)
class KnowledgeSource:
    document_name: str = ""
    document_id: str = ""
    dataset_id: str = ""
    chunk_id: str = ""
    similarity: float | None = None

    def display_name(self) -> str:
        return self.document_name or self.document_id or self.chunk_id or self.dataset_id or "未知来源"

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "document_name": self.document_name,
            "document_id": self.document_id,
            "dataset_id": self.dataset_id,
            "chunk_id": self.chunk_id,
        }
        if self.similarity is not None:
            payload["similarity"] = self.similarity
        return {key: value for key, value in payload.items() if value not in ("", None)}


@dataclass(frozen=True)
class KnowledgeChunk:
    content: str
    source: KnowledgeSource
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeResult:
    result_type: str
    title: str | None
    speak_text: str
    summary: str | None = None
    bullets: list[str] = field(default_factory=list)
    sources: list[KnowledgeSource] = field(default_factory=list)
    source_summary: str = ""
    provider: str = "local_ragflow_direct"
    reason: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class KnowledgeProviderStatus:
    name: str
    status: str
    source: str = "code_default"
    notes: str = ""


class KnowledgeProviderError(Exception):
    code = "KNOWLEDGE_PROVIDER_ERROR"
    user_message = "知识库直连暂不可用，请稍后重试。"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.user_message)


class KnowledgeConfigError(KnowledgeProviderError):
    code = "KNOWLEDGE_CONFIG_ERROR"
    user_message = "知识库直连配置不完整，请检查后端 RAGFlow 配置。"


class KnowledgeRetrievalError(KnowledgeProviderError):
    code = "KNOWLEDGE_RETRIEVAL_ERROR"
    user_message = "知识库检索暂不可用，请稍后重试。"


class KnowledgeRetriever(Protocol):
    name: str

    def retrieve(self, question: str) -> list[KnowledgeChunk]:
        ...


class RagflowKnowledgeRetriever:
    name = "ragflow"

    def __init__(
        self,
        *,
        base_url: str = "",
        mcp_url: str = "",
        api_key: str = "",
        transport: str = "api",
        dataset_ids: list[str] | None = None,
        dataset_name: str = "",
        page_size: int = 3,
        top_k: int = 16,
        similarity_threshold: float = 0.35,
        max_chunk_chars: int = 1200,
        timeout_seconds: int = 15,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.mcp_url = mcp_url.strip()
        self.api_key = api_key.strip()
        self.transport = _normalize_transport(transport, base_url=self.base_url, mcp_url=self.mcp_url)
        self.dataset_ids = [item.strip() for item in (dataset_ids or []) if item.strip()]
        self.dataset_name = dataset_name.strip()
        self.page_size = max(1, min(int(page_size or 3), 10))
        self.top_k = max(1, min(int(top_k or 16), 64))
        self.similarity_threshold = max(0.0, min(float(similarity_threshold), 1.0))
        self.max_chunk_chars = max(200, min(int(max_chunk_chars or 1200), 4000))
        self.timeout_seconds = max(1, min(int(timeout_seconds or 15), 60))

    def retrieve(self, question: str) -> list[KnowledgeChunk]:
        query = question.strip()
        if not query:
            return []
        if self.transport == "mcp":
            return self._retrieve_mcp(query)
        return self._retrieve_api(query)

    def _retrieve_api(self, question: str) -> list[KnowledgeChunk]:
        if not self.base_url:
            raise KnowledgeConfigError("RAGFLOW_BASE_URL is required for API retrieval")
        if not _usable_secret(self.api_key):
            raise KnowledgeConfigError("RAGFLOW_API_KEY is required for API retrieval")

        dataset_ids = self.dataset_ids or self._resolve_dataset_ids()
        if not dataset_ids:
            raise KnowledgeConfigError("No RAGFlow dataset IDs are configured or resolved")

        payload = {
            "dataset_ids": dataset_ids,
            "question": question,
            "page": 1,
            "size": self.page_size,
            "page_size": self.page_size,
            "similarity_threshold": self.similarity_threshold,
            "vector_similarity_weight": 0.3,
            "top_k": self.top_k,
            "keyword": False,
        }
        try:
            with httpx.Client(timeout=self._timeout(), follow_redirects=True) as client:
                response = client.post(
                    _join_url(self.base_url, "/api/v1/datasets/search"),
                    headers=self._api_headers(),
                    json=payload,
                )
                response.raise_for_status()
                decoded = response.json()
        except (httpx.TimeoutException, httpx.HTTPError, ValueError) as exc:
            raise KnowledgeRetrievalError("RAGFlow API retrieval failed") from exc

        if isinstance(decoded, dict) and decoded.get("code") not in (0, "0", None):
            raise KnowledgeRetrievalError("RAGFlow API returned a non-zero code")
        return _chunks_from_payload(decoded, max_chunk_chars=self.max_chunk_chars)

    def _resolve_dataset_ids(self) -> list[str]:
        if not self.dataset_name:
            return []
        try:
            with httpx.Client(timeout=self._timeout(), follow_redirects=True) as client:
                response = client.get(
                    _join_url(self.base_url, "/api/v1/datasets"),
                    headers=self._api_headers(),
                    params={"page": 1, "page_size": 100},
                )
                response.raise_for_status()
                decoded = response.json()
        except (httpx.TimeoutException, httpx.HTTPError, ValueError) as exc:
            raise KnowledgeRetrievalError("RAGFlow dataset lookup failed") from exc

        datasets = _extract_dataset_items(decoded)
        matched = [
            str(item.get("id") or "").strip()
            for item in datasets
            if str(item.get("name") or "").strip() == self.dataset_name
        ]
        return [item for item in matched if item]

    def _retrieve_mcp(self, question: str) -> list[KnowledgeChunk]:
        if not self.mcp_url:
            raise KnowledgeConfigError("RAGFLOW_MCP_URL is required for MCP retrieval")

        arguments = {
            "dataset_ids": self.dataset_ids,
            "document_ids": [],
            "question": question,
            "page": 1,
            "page_size": self.page_size,
            "similarity_threshold": self.similarity_threshold,
            "top_k": self.top_k,
            "keyword": False,
        }
        request_payload = {
            "jsonrpc": "2.0",
            "id": "knowledge-direct-retrieval",
            "method": "tools/call",
            "params": {
                "name": "ragflow_retrieval",
                "arguments": arguments,
            },
        }
        try:
            with httpx.Client(timeout=self._timeout(), follow_redirects=True) as client:
                response = client.post(
                    self.mcp_url,
                    headers=self._mcp_headers(),
                    json=request_payload,
                )
                response.raise_for_status()
                decoded = _decode_mcp_response(response)
        except (httpx.TimeoutException, httpx.HTTPError, ValueError) as exc:
            raise KnowledgeRetrievalError("RAGFlow MCP retrieval failed") from exc

        return _chunks_from_payload(decoded, max_chunk_chars=self.max_chunk_chars)

    def _api_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _mcp_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if _usable_secret(self.api_key):
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(float(self.timeout_seconds), read=float(self.timeout_seconds))


class StaticKnowledgeRetriever:
    """Small deterministic retriever used by smoke tests and local provider injection."""

    name = "static"

    def __init__(self, chunks: list[KnowledgeChunk]) -> None:
        self.chunks = chunks

    def retrieve(self, question: str) -> list[KnowledgeChunk]:
        terms = _query_terms(question)
        scored: list[tuple[int, KnowledgeChunk]] = []
        for chunk in self.chunks:
            haystack = _normalize_text(chunk.content)
            score = sum(1 for term in terms if term in haystack)
            if score > 0:
                scored.append((score, chunk))
        if not terms:
            return self.chunks[:3]
        return [chunk for _, chunk in sorted(scored, key=lambda item: item[0], reverse=True)[:3]]


class SourceBoundSummarizer:
    name = "source_bound_extractive"

    def __init__(
        self,
        *,
        require_sources: bool = True,
        fallback_text: str = DEFAULT_KNOWLEDGE_FALLBACK_TEXT,
        max_answer_chars: int = 800,
    ) -> None:
        self.require_sources = require_sources
        self.fallback_text = fallback_text or DEFAULT_KNOWLEDGE_FALLBACK_TEXT
        self.max_answer_chars = max(120, min(int(max_answer_chars or 800), 1500))

    def summarize(self, question: str, chunks: list[KnowledgeChunk]) -> KnowledgeResult:
        usable_chunks = [chunk for chunk in chunks if chunk.content.strip()]
        if self.require_sources and not usable_chunks:
            return self._fallback("KNOWLEDGE_NO_SOURCES")

        selected = self._select_sentences(question, usable_chunks)
        if not selected:
            return self._fallback("KNOWLEDGE_NO_EVIDENCE")

        sentences = [item[0] for item in selected]
        speak_text = "根据知识库资料，" + "；".join(sentences)
        speak_text = _trim_text(speak_text, self.max_answer_chars)
        sources = _unique_sources([item[1].source for item in selected])
        source_summary = _source_summary(sources)
        return KnowledgeResult(
            result_type="answer",
            title=_title_from_question(question),
            speak_text=speak_text,
            summary=f"基于 {source_summary} 的检索结果回答。" if source_summary else "基于知识库检索结果回答。",
            bullets=sentences[:5],
            sources=sources,
            source_summary=source_summary,
            provider="local_ragflow_direct",
        )

    def _fallback(self, code: str) -> KnowledgeResult:
        return KnowledgeResult(
            result_type="fallback",
            title=None,
            speak_text=self.fallback_text,
            reason=code,
            error_code=code,
        )

    def _select_sentences(
        self,
        question: str,
        chunks: list[KnowledgeChunk],
    ) -> list[tuple[str, KnowledgeChunk]]:
        terms = _query_terms(question)
        candidates: list[tuple[int, int, str, KnowledgeChunk]] = []
        order = 0
        for chunk in chunks[:8]:
            text = _strip_executable_blocks(chunk.content)
            for sentence in _sentences(text):
                if _looks_executable(sentence):
                    continue
                score = _sentence_score(sentence, terms)
                if score <= 0 and terms:
                    continue
                candidates.append((score, -order, sentence, chunk))
                order += 1
        if not candidates and chunks:
            for sentence in _sentences(_strip_executable_blocks(chunks[0].content)):
                if not _looks_executable(sentence):
                    candidates.append((1, -order, sentence, chunks[0]))
                    order += 1
                if len(candidates) >= 2:
                    break
        ranked = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)
        selected: list[tuple[str, KnowledgeChunk]] = []
        seen = set()
        for _, _, sentence, chunk in ranked:
            normalized = _normalize_text(sentence)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            selected.append((sentence, chunk))
            if len(selected) >= 4:
                break
        return selected


class KnowledgeDirectProvider:
    name = "local_ragflow_direct"

    def __init__(
        self,
        *,
        retriever: KnowledgeRetriever,
        summarizer: SourceBoundSummarizer,
        enabled: bool = False,
        fallback_text: str = DEFAULT_KNOWLEDGE_FALLBACK_TEXT,
    ) -> None:
        self.retriever = retriever
        self.summarizer = summarizer
        self.enabled = enabled
        self.fallback_text = fallback_text or DEFAULT_KNOWLEDGE_FALLBACK_TEXT

    def query(self, text: str) -> KnowledgeResult | None:
        if not self.enabled or not _looks_like_knowledge_query(text):
            return None
        chunks = self.retriever.retrieve(text)
        return self.summarizer.summarize(text, chunks)

    def status(self) -> KnowledgeProviderStatus:
        return KnowledgeProviderStatus(
            name=self.name,
            status="implemented" if self.enabled else "available_disabled",
            notes=(
                "RAGFlow 只检索 chunks/metadata; SourceBoundSummarizer 强制基于来源回答, "
                "require_sources=true, no_evidence_policy=fallback。"
            ),
        )


def _chunks_from_payload(payload: Any, *, max_chunk_chars: int) -> list[KnowledgeChunk]:
    chunks_payload = _find_chunks(payload)
    chunks = [_chunk_from_dict(item, max_chunk_chars=max_chunk_chars) for item in chunks_payload]
    return [chunk for chunk in chunks if chunk is not None]


def _find_chunks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        chunks: list[dict[str, Any]] = []
        for item in payload:
            chunks.extend(_find_chunks(item))
        return chunks
    if isinstance(payload, str):
        parsed = _try_json(payload)
        return _find_chunks(parsed) if parsed is not None else []
    if not isinstance(payload, dict):
        return []
    if "chunks" in payload and isinstance(payload["chunks"], list):
        return [item for item in payload["chunks"] if isinstance(item, dict)]
    if "content" in payload and isinstance(payload["content"], list):
        chunks: list[dict[str, Any]] = []
        for item in payload["content"]:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                chunks.extend(_find_chunks(item["text"]))
        return chunks
    for key in ("result", "data"):
        if key in payload:
            chunks = _find_chunks(payload[key])
            if chunks:
                return chunks
    return []


def _chunk_from_dict(item: dict[str, Any], *, max_chunk_chars: int) -> KnowledgeChunk | None:
    content = _clean_content(
        item.get("content")
        or item.get("content_with_weight")
        or item.get("text")
        or item.get("chunk")
        or ""
    )
    if not content:
        return None
    source = KnowledgeSource(
        document_name=str(
            item.get("document_name")
            or item.get("doc_name")
            or item.get("document_keyword")
            or item.get("name")
            or ""
        ),
        document_id=str(item.get("document_id") or item.get("doc_id") or ""),
        dataset_id=str(item.get("dataset_id") or item.get("kb_id") or ""),
        chunk_id=str(item.get("chunk_id") or item.get("id") or ""),
        similarity=_to_float_or_none(
            item.get("similarity")
            or item.get("similarity_score")
            or item.get("score")
            or item.get("vector_similarity")
        ),
    )
    return KnowledgeChunk(
        content=content[:max_chunk_chars],
        source=source,
        metadata={
            key: value
            for key, value in item.items()
            if key
            not in {
                "content",
                "content_with_weight",
                "text",
                "chunk",
            }
        },
    )


def _decode_mcp_response(response: httpx.Response) -> Any:
    text = response.text.strip()
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" in content_type or text.startswith("event:") or text.startswith("data:"):
        payloads = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("data:"):
                continue
            data = stripped.removeprefix("data:").strip()
            if data and data != "[DONE]":
                payloads.append(_try_json(data) or data)
        return payloads
    return response.json()


def _extract_dataset_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "result", "items", "records", "datasets"):
        if key in payload:
            items = _extract_dataset_items(payload[key])
            if items:
                return items
    return []


def _looks_like_knowledge_query(text: str) -> bool:
    normalized = _normalize_text(text)
    if not normalized:
        return False
    screen_terms = ("切换", "打开", "返回", "回到", "跳转", "翻页", "页面")
    if any(term in normalized for term in screen_terms):
        return False
    knowledge_terms = (
        "是什么",
        "有哪些",
        "说明",
        "介绍",
        "流程",
        "制度",
        "规范",
        "要求",
        "资料",
        "新闻",
        "调研",
        "最近",
        "怎么",
        "如何",
        "为什么",
        "请问",
    )
    return any(term in normalized for term in knowledge_terms)


def _query_terms(text: str) -> list[str]:
    normalized = _normalize_text(text)
    stop_terms = {
        "是什么",
        "有哪些",
        "请问",
        "一下",
        "这个",
        "那个",
        "我们",
        "你们",
        "可以",
        "怎么",
        "如何",
        "为什么",
    }
    for term in stop_terms:
        normalized = normalized.replace(term, "")
    terms = {normalized[index : index + 2] for index in range(max(0, len(normalized) - 1))}
    terms.update(normalized[index : index + 3] for index in range(max(0, len(normalized) - 2)))
    return [term for term in terms if len(term) >= 2]


def _sentence_score(sentence: str, terms: list[str]) -> int:
    normalized = _normalize_text(sentence)
    if not terms:
        return 1
    return sum(1 for term in terms if term in normalized)


def _sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[。！？!?；;])|\n+", cleaned)
    sentences = [part.strip(" -\t\r\n") for part in parts if part.strip(" -\t\r\n")]
    return [_trim_text(sentence, 180) for sentence in sentences]


def _strip_executable_blocks(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    return text


def _looks_executable(text: str) -> bool:
    patterns = (
        r"\bselect\b",
        r"\binsert\b",
        r"\bdelete\b",
        r"\bupdate\b",
        r"\bpython\b",
        r"\bpowershell\b",
        r"\bshell\b",
        r"function\s*\(",
        r"=>",
        r"<script",
        r"```",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _unique_sources(sources: list[KnowledgeSource]) -> list[KnowledgeSource]:
    unique: list[KnowledgeSource] = []
    seen = set()
    for source in sources:
        key = (
            source.document_name,
            source.document_id,
            source.dataset_id,
            source.chunk_id,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(source)
        if len(unique) >= 5:
            break
    return unique


def _source_summary(sources: list[KnowledgeSource]) -> str:
    names = [source.display_name() for source in sources]
    return "、".join(names[:5])


def _title_from_question(question: str) -> str:
    title = re.sub(r"[？?。!！\s]+", "", question).strip()
    return _trim_text(title or "知识库回答", 24)


def _trim_text(text: str, max_chars: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max_chars - 1].rstrip("，,；;。 ") + "。"


def _clean_content(value: Any) -> str:
    text = str(value or "").strip()
    text = _strip_executable_blocks(text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_text(text: str) -> str:
    return re.sub(r"[\s，。！？!?；;：:、,.\"'“”‘’（）()\[\]【】<>《》]+", "", text).strip()


def _try_json(value: str) -> Any | None:
    try:
        return json.loads(value)
    except ValueError:
        return None


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _normalize_transport(value: str, *, base_url: str, mcp_url: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"mcp", "streamable_http"}:
        return "mcp"
    if normalized in {"api", "ragflow_api", "retrieval_api"}:
        return "api"
    return "api" if base_url else ("mcp" if mcp_url else "api")


def _usable_secret(value: str) -> bool:
    normalized = str(value or "").strip()
    return bool(normalized and normalized.lower() not in {"replace_me", "changeme", "none", "null", "***"})
