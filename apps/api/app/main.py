import base64
import json
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from time import sleep
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import PlainTextResponse
from fastapi.responses import StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.models import (
    AsrTranscribeRequest,
    AsrTranscribeResponse,
    ChatRequest,
    ChatResponse,
    ConfigAuditResponse,
    ConfigEffectiveResponse,
    ConfigOverridePayload,
    ConfigOverrideResponse,
    ConfigReloadResponse,
    ConfigSchemaResponse,
    ConfigValidateResponse,
    DemoConfigResponse,
    ErrorDetail,
    HealthResponse,
    OpsDependenciesResponse,
    OpsDependencyStatus,
    OpsErrorsResponse,
    OpsHealthResponse,
    OpsMetricsResponse,
    OpsSessionDetailResponse,
    OpsSessionsResponse,
    ScreenActionsResponse,
    ScreenExecuteRequest,
    ScreenExecuteResponse,
    TtsSynthesizeRequest,
    TtsSynthesizeResponse,
    WakeConfigResponse,
)
from app.services.asr_provider import AsrProviderError, build_asr_provider
from app.services.ask_metrics import AskMetricsService
from app.services.config_overrides import ConfigOverrideService
from app.services.config_snapshot import build_config_effective, build_config_schema
from app.services.dora_client import DoraClient, DoraClientError
from app.services.dora_normalizer import dora_error_response, normalize_dora_output
from app.services.knowledge import build_knowledge_service, knowledge_error_response
from app.services.knowledge_provider import KnowledgeProviderError
from app.services.mock_dora import MockDoraService
from app.services.screen_actions import ScreenActionService
from app.services.screen_resolver import ScreenControlResolver
from app.services.session_log import SessionLogStore
from app.services.tts_provider import TtsProviderError, build_tts_provider
from app.services.wake_words import WakeWordService


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

config_override_service = ConfigOverrideService(settings.config_overrides_dir)
action_service = ScreenActionService(
    settings.action_whitelist_path,
    overrides=config_override_service.screen_action_overrides(),
)
screen_resolver = ScreenControlResolver(action_service)
mock_dora = MockDoraService(settings.demo_cases_path, action_service)
wake_words = WakeWordService(settings.wake_words_path)
ask_metrics = AskMetricsService(settings.ask_metrics_data_dir, settings.ask_metrics_config_path)
knowledge_service = build_knowledge_service(settings)
asr_provider = build_asr_provider(
    enable_mock=settings.enable_mock_asr,
    provider_name=settings.asr_provider,
    api_key=settings.asr_api_key,
    model=settings.asr_model,
    ws_url=settings.asr_ws_url,
    audio_format=settings.asr_audio_format,
    sample_rate=settings.asr_sample_rate,
    timeout_seconds=settings.asr_timeout_seconds,
)
tts_provider = build_tts_provider(
    enable_mock=settings.enable_mock_tts,
    provider_name=settings.tts_provider,
    cache_dir=settings.tts_cache_dir,
    default_voice=settings.tts_voice,
    api_key=settings.tts_api_key,
    model=settings.tts_model,
    ws_url=settings.tts_ws_url,
    default_format=settings.tts_audio_format,
    sample_rate=settings.tts_sample_rate,
    timeout_seconds=settings.tts_timeout_seconds,
)
dora_client = DoraClient(
    base_url=settings.dora_base_url,
    api_key=settings.dora_api_key,
    agent_id=settings.dora_agent_id,
    agent_name=settings.dora_agent_name,
    channel_type=settings.dora_channel_type,
    timeout_seconds=settings.dora_timeout_seconds,
)
session_logs = SessionLogStore(settings.sqlite_path)
session_logs.initialize()

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
            },
            "request_id": _request_id(request),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
            "request_id": _request_id(request),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request failure")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "服务临时不可用，请稍后再试。",
            },
            "request_id": _request_id(request),
        },
    )


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
    )


@app.get("/api/ops/health", response_model=OpsHealthResponse)
def ops_health() -> OpsHealthResponse:
    return OpsHealthResponse(
        status="ok" if session_logs.is_available() else "error",
        app=settings.app_name,
        version=settings.app_version,
        customer_id=settings.customer_id,
        time=_now_iso(),
    )


@app.get("/api/ops/dependencies", response_model=OpsDependenciesResponse)
def ops_dependencies() -> OpsDependenciesResponse:
    dependencies = _ops_dependency_statuses()
    return OpsDependenciesResponse(
        status=_overall_ops_status(dependencies),
        dependencies=dependencies,
    )


@app.get("/api/ops/sessions", response_model=OpsSessionsResponse)
def ops_sessions(limit: int = Query(default=20, ge=1, le=100)) -> OpsSessionsResponse:
    return OpsSessionsResponse(sessions=session_logs.list_sessions(limit=limit))


@app.get("/api/ops/session/{session_id}", response_model=OpsSessionDetailResponse)
def ops_session_detail(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> OpsSessionDetailResponse:
    return OpsSessionDetailResponse(
        session_id=session_id,
        events=session_logs.list_session_events(session_id, limit=limit),
    )


@app.get("/api/ops/errors", response_model=OpsErrorsResponse)
def ops_errors(limit: int = Query(default=30, ge=1, le=100)) -> OpsErrorsResponse:
    return OpsErrorsResponse(errors=session_logs.list_errors(limit=limit))


@app.get("/api/ops/metrics", response_model=OpsMetricsResponse)
def ops_metrics(recent_limit: int = Query(default=30, ge=1, le=100)) -> OpsMetricsResponse:
    return OpsMetricsResponse(**session_logs.metrics(recent_limit=recent_limit))


@app.get("/api/ops/export")
def ops_export(limit: int = Query(default=50, ge=1, le=200)) -> PlainTextResponse:
    content = _ops_export_markdown(limit=limit)
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="zt-ops-log-export.md"'},
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    started_at = perf_counter()
    response = _chat_response(request)
    screen_action = None
    if response.action is not None:
        screen_action = {"action_id": response.action.id, "success": None}

    _safe_log_chat(
        session_id=response.session_id,
        message_id=response.message_id,
        user_text=request.text,
        intent_type=response.type,
        dora_response=response,
        screen_action=screen_action,
        error=response.error.model_dump() if response.error else None,
        started_at=started_at,
    )
    return response


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        _chat_stream_events(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/api/asr/transcribe", response_model=AsrTranscribeResponse)
def transcribe_audio(request: AsrTranscribeRequest) -> AsrTranscribeResponse:
    try:
        result = asr_provider.transcribe(
            mock_text=request.mock_text,
            audio_base64=request.audio_base64,
            audio_format=request.audio_format,
        )
        return AsrTranscribeResponse(
            success=True,
            session_id=request.session_id,
            text=result.text,
            provider=result.provider,
            mock=result.mock,
            duration_ms=result.duration_ms,
        )
    except AsrProviderError as exc:
        logger.warning("ASR transcribe failed with code %s", exc.code)
        return AsrTranscribeResponse(
            success=False,
            session_id=request.session_id,
            text="",
            provider=asr_provider.provider_name,
            mock=asr_provider.is_mock,
            error=ErrorDetail(code=exc.code, message=exc.user_message),
        )


@app.get("/api/wake/config", response_model=WakeConfigResponse)
def get_wake_config() -> WakeConfigResponse:
    return wake_words.get_config()


@app.get("/api/demo/config", response_model=DemoConfigResponse)
def get_demo_config() -> DemoConfigResponse:
    return DemoConfigResponse(
        stable_mode=settings.demo_stable_mode,
        project_id=settings.project_id,
        project_name=settings.project_name,
        product_name=settings.product_name,
        customer_id=settings.customer_id,
        customer_name=settings.customer_name,
        scenario_name=settings.scenario_name,
        assistant_name=settings.assistant_name,
        ask_metrics_mode=_ask_metrics_mode(),
        mock={
            "dora": settings.enable_mock_dora,
            "asr": settings.enable_mock_asr,
            "tts": settings.enable_mock_tts,
            "fvs": settings.enable_mock_fvs,
        },
        questions=mock_dora.list_demo_questions(),
        notice=(
            "演示稳态模式已开启，外部 Dora 失败时会优先使用本地演示兜底。"
            if settings.demo_stable_mode
            else "演示稳态模式未开启，系统按当前真实/Mock 开关运行。"
        ),
    )


@app.get("/api/config/effective", response_model=ConfigEffectiveResponse)
def get_config_effective() -> ConfigEffectiveResponse:
    return ConfigEffectiveResponse(**build_config_effective(settings, action_service))


@app.get("/api/config/schema", response_model=ConfigSchemaResponse)
def get_config_schema() -> ConfigSchemaResponse:
    return ConfigSchemaResponse(**build_config_schema())


@app.get("/api/config/overrides", response_model=ConfigOverrideResponse)
def get_config_overrides() -> ConfigOverrideResponse:
    return ConfigOverrideResponse(**config_override_service.active_response(access=_config_access_info()))


@app.post("/api/config/validate", response_model=ConfigValidateResponse)
def validate_config_overrides(payload: ConfigOverridePayload) -> ConfigValidateResponse:
    return ConfigValidateResponse(
        **config_override_service.validate(
            payload.overrides,
            base_action_path=settings.action_whitelist_path,
            dry_run=False,
        )
    )


@app.post("/api/config/test", response_model=ConfigValidateResponse)
def dry_run_config_overrides(payload: ConfigOverridePayload) -> ConfigValidateResponse:
    return ConfigValidateResponse(
        **config_override_service.validate(
            payload.overrides,
            base_action_path=settings.action_whitelist_path,
            dry_run=True,
        )
    )


@app.put("/api/config/overrides", response_model=ConfigValidateResponse)
def save_config_overrides(payload: ConfigOverridePayload, fastapi_request: Request) -> ConfigValidateResponse:
    operator = _require_config_admin(fastapi_request, payload)
    reason = _config_reason(payload)
    return ConfigValidateResponse(
        **config_override_service.save(
            payload.overrides,
            operator=operator,
            reason=reason,
            base_action_path=settings.action_whitelist_path,
        )
    )


@app.post("/api/config/reload", response_model=ConfigReloadResponse)
def reload_config(payload: ConfigOverridePayload, fastapi_request: Request) -> ConfigReloadResponse:
    operator = _require_config_admin(fastapi_request, payload)
    reason = _config_reason(payload)
    validation = config_override_service.validate(
        config_override_service.read_active_overrides(),
        base_action_path=settings.action_whitelist_path,
        dry_run=True,
    )
    if not validation["ok"]:
        config_override_service.append_audit(
            action="reload_rejected",
            operator=operator,
            reason=reason,
            ok=False,
            summary=validation["summary"],
            errors=validation["errors"],
        )
        return ConfigReloadResponse(
            success=False,
            reloaded_at=_now_iso(),
            summary=validation["summary"],
            error=ErrorDetail(code="CONFIG_RELOAD_REJECTED", message="Active overrides failed validation"),
        )
    summary = _reload_runtime_services()
    config_override_service.append_audit(
        action="reload",
        operator=operator,
        reason=reason,
        ok=True,
        summary=summary,
        errors=[],
    )
    return ConfigReloadResponse(success=True, reloaded_at=_now_iso(), summary=summary)


@app.get("/api/config/audit", response_model=ConfigAuditResponse)
def get_config_audit(limit: int = Query(default=50, ge=1, le=200)) -> ConfigAuditResponse:
    return ConfigAuditResponse(events=config_override_service.audit_events(limit=limit))


@app.post("/api/tts", response_model=TtsSynthesizeResponse)
def synthesize_tts(request: TtsSynthesizeRequest) -> TtsSynthesizeResponse:
    voice = request.voice or settings.tts_voice
    audio_format = request.format or settings.tts_audio_format
    try:
        result = tts_provider.synthesize(
            text=request.text,
            voice=voice,
            audio_format=audio_format,
        )
        return TtsSynthesizeResponse(
            success=True,
            audio_url=result.audio_url,
            audio_id=result.audio_id,
            duration_ms=result.duration_ms,
            provider=result.provider,
            voice=result.voice,
            format=result.format,
            mock=result.mock,
        )
    except TtsProviderError as exc:
        logger.warning("TTS synthesize failed with code %s", exc.code)
        return TtsSynthesizeResponse(
            success=False,
            provider=tts_provider.provider_name,
            voice=voice,
            format=audio_format,
            mock=tts_provider.is_mock,
            error=ErrorDetail(code=exc.code, message=exc.user_message),
        )


@app.post("/api/tts/stream")
def stream_tts(request: TtsSynthesizeRequest) -> StreamingResponse:
    return StreamingResponse(
        _tts_stream_events(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/tts/audio/{audio_id}")
def get_tts_audio(audio_id: str) -> FileResponse:
    audio_path = tts_provider.get_audio_path(audio_id)
    if audio_path is None:
        raise StarletteHTTPException(status_code=404, detail="TTS audio not found")
    return FileResponse(path=audio_path, media_type=_audio_media_type(audio_path.suffix), filename=audio_id)


async def _tts_stream_events(request: TtsSynthesizeRequest):
    voice = request.voice or settings.tts_voice
    audio_format = request.format or settings.tts_streaming_audio_format or settings.tts_audio_format
    if not settings.tts_streaming_enabled:
        yield _sse(
            "tts_error",
            {
                "code": "TTS_STREAMING_DISABLED",
                "message": "TTS 真流式未启用，已回退到分段播报。",
                "fallback": settings.tts_streaming_fallback,
            },
        )
        yield _sse("end", {"ok": False, "chunks": 0, "fallback": settings.tts_streaming_fallback})
        return

    started_at = perf_counter()
    chunk_count = 0
    metadata_sent = False
    try:
        async for chunk in tts_provider.stream_synthesize(
            text=request.text,
            voice=voice,
            audio_format=audio_format,
        ):
            if not metadata_sent:
                yield _sse(
                    "metadata",
                    {
                        "provider": chunk.provider,
                        "voice": chunk.voice,
                        "format": chunk.format,
                        "mime_type": chunk.mime_type,
                        "sample_rate": chunk.sample_rate,
                        "mock": chunk.mock,
                        "fallback": settings.tts_streaming_fallback,
                    },
                )
                metadata_sent = True
            chunk_count += 1
            yield _sse(
                "audio_chunk",
                {
                    "index": chunk.index,
                    "audio_base64": base64.b64encode(chunk.audio).decode("ascii"),
                    "mime_type": chunk.mime_type,
                    "provider": chunk.provider,
                    "format": chunk.format,
                    "sample_rate": chunk.sample_rate,
                    "duration_ms": int((perf_counter() - started_at) * 1000),
                    "mock": chunk.mock,
                },
            )
        yield _sse(
            "end",
            {
                "ok": True,
                "chunks": chunk_count,
                "duration_ms": int((perf_counter() - started_at) * 1000),
                "fallback": settings.tts_streaming_fallback,
            },
        )
    except TtsProviderError as exc:
        logger.warning("TTS stream failed with code %s", exc.code)
        yield _sse(
            "tts_error",
            {
                "code": exc.code,
                "message": exc.user_message,
                "fallback": settings.tts_streaming_fallback,
            },
        )
        yield _sse("end", {"ok": False, "chunks": chunk_count, "fallback": settings.tts_streaming_fallback})
    except Exception:
        logger.exception("Unexpected TTS stream failure")
        yield _sse(
            "tts_error",
            {
                "code": "TTS_STREAM_ERROR",
                "message": "TTS 真流式播放失败，已回退到分段播报。",
                "fallback": settings.tts_streaming_fallback,
            },
        )
        yield _sse("end", {"ok": False, "chunks": chunk_count, "fallback": settings.tts_streaming_fallback})


def _chat_response(request: ChatRequest) -> ChatResponse:
    screen_response = _safe_screen_control_response(request)
    if screen_response is not None:
        return screen_response

    metrics_mode = _ask_metrics_mode()

    if metrics_mode == "excel":
        metrics_response = _safe_ask_metrics_response(request)
        if metrics_response is not None:
            return metrics_response
        return _knowledge_or_dora_response(request)

    if metrics_mode == "dora":
        return _knowledge_or_dora_response(request)

    response = _knowledge_or_dora_response(request)
    if response.type == "fallback" and _should_auto_metrics_fallback(response):
        metrics_response = _safe_ask_metrics_response(request, message_id=response.message_id)
        if metrics_response is not None:
            return metrics_response
    return response


def _knowledge_or_dora_response(request: ChatRequest, *, message_id: str | None = None) -> ChatResponse:
    knowledge_response = _safe_knowledge_response(request, message_id=message_id)
    if knowledge_response is not None:
        return knowledge_response
    return _dora_or_mock_response(request, message_id=message_id)


def _safe_screen_control_response(request: ChatRequest, *, message_id: str | None = None) -> ChatResponse | None:
    try:
        resolved = screen_resolver.resolve(request.text)
        if resolved is None:
            return None
        return screen_resolver.to_chat_response(
            request,
            resolved,
            message_id=message_id or f"msg-{uuid4().hex[:12]}",
        )
    except Exception:
        logger.warning("Screen control resolver failed", exc_info=True)
        return None


def _dora_or_mock_response(request: ChatRequest, *, message_id: str | None = None) -> ChatResponse:
    if settings.enable_mock_dora:
        return _with_message_id(mock_dora.respond(request), message_id)

    response_message_id = message_id or f"msg-{uuid4().hex[:12]}"
    try:
        result = dora_client.sse_chat(request, message_id=response_message_id)
        return normalize_dora_output(
            raw_output=result.raw_output,
            request=request,
            action_service=action_service,
            message_id=result.message_id,
        )
    except DoraClientError as exc:
        logger.warning("Dora chat failed with code %s", exc.code)
        if settings.demo_stable_mode:
            return _demo_stable_response(request, message_id=response_message_id, cause_code=exc.code)
        return dora_error_response(
            request=request,
            message_id=response_message_id,
            code=exc.code,
            speak_text=exc.user_message,
            reason=exc.code,
        )


def _safe_ask_metrics_response(request: ChatRequest, *, message_id: str | None = None) -> ChatResponse | None:
    try:
        return ask_metrics.respond(request, message_id=message_id)
    except Exception:
        logger.warning("Ask metrics adapter failed", exc_info=True)
        return dora_error_response(
            request=request,
            message_id=message_id or f"msg-{uuid4().hex[:12]}",
            code="ASK_METRICS_DATA_UNAVAILABLE",
            speak_text="问数演示数据暂不可用，请检查 Excel 数据文件后重试。",
            reason="ASK_METRICS_DATA_UNAVAILABLE",
        )


def _safe_knowledge_response(request: ChatRequest, *, message_id: str | None = None) -> ChatResponse | None:
    try:
        return knowledge_service.respond(request, message_id=message_id)
    except KnowledgeProviderError as exc:
        logger.warning("Knowledge direct adapter failed with code %s", exc.code)
        return knowledge_error_response(request, message_id=message_id, exc=exc)
    except Exception:
        logger.warning("Knowledge direct adapter failed unexpectedly", exc_info=True)
        return dora_error_response(
            request=request,
            message_id=message_id or f"msg-{uuid4().hex[:12]}",
            code="KNOWLEDGE_DIRECT_ERROR",
            speak_text="知识库直连暂不可用，请稍后重试。",
            reason="KNOWLEDGE_DIRECT_ERROR",
        )


def _demo_stable_response(request: ChatRequest, *, message_id: str, cause_code: str) -> ChatResponse:
    metrics_response = _safe_ask_metrics_response(request, message_id=message_id)
    if metrics_response is not None and metrics_response.type != "fallback":
        return metrics_response

    mock_response = _with_message_id(mock_dora.respond(request), message_id)
    if mock_response.type != "fallback":
        return mock_response

    return dora_error_response(
        request=request,
        message_id=message_id,
        code="DEMO_STABLE_FALLBACK",
        speak_text="演示模式下外部服务暂不可用，当前问题未命中本地演示兜底，请换一个演示问题或稍后重试。",
        reason=cause_code,
    )


def _with_message_id(response: ChatResponse, message_id: str | None) -> ChatResponse:
    if not message_id or response.message_id == message_id:
        return response
    return response.model_copy(update={"message_id": message_id})


def _ask_metrics_mode() -> str:
    mode = settings.ask_metrics_mode.strip().lower()
    if mode not in {"excel", "dora", "auto"}:
        logger.warning("Unsupported ASK_METRICS_MODE=%s, fallback to excel", settings.ask_metrics_mode)
        return "excel"
    return mode


def _should_auto_metrics_fallback(response: ChatResponse) -> bool:
    if response.error and response.error.code.startswith("KNOWLEDGE_"):
        return False
    return True


def _chat_stream_events(request: ChatRequest):
    started_at = perf_counter()
    message_id = f"msg-{uuid4().hex[:12]}"
    yield _sse("metadata", {"session_id": request.session_id, "message_id": message_id})

    with ThreadPoolExecutor(max_workers=2) as executor:
        tts_jobs: list[dict] = []
        segmenter = _SpeechSegmenter()
        speak_extractor = _SpeakTextExtractor()
        sse_events = []
        scheduled_count = 0
        response: ChatResponse | None = None

        def schedule_tts(text: str):
            nonlocal scheduled_count
            segment_text = text.strip()
            if not segment_text:
                return
            index = scheduled_count
            scheduled_count += 1
            future = executor.submit(
                tts_provider.synthesize,
                text=segment_text,
                voice=settings.tts_voice,
                audio_format=settings.tts_audio_format,
            )
            tts_jobs.append({"index": index, "text": segment_text, "future": future, "emitted": False})

        def emit_ready_jobs(block: bool = False):
            while True:
                emitted_any = False
                for job in tts_jobs:
                    if job["emitted"]:
                        continue
                    future: Future = job["future"]
                    if not future.done():
                        continue
                    job["emitted"] = True
                    emitted_any = True
                    try:
                        result = future.result()
                        yield _sse(
                            "tts_ready",
                            {
                                "index": job["index"],
                                "text": job["text"],
                                "audio_url": result.audio_url,
                                "audio_id": result.audio_id,
                                "duration_ms": result.duration_ms,
                                "provider": result.provider,
                                "format": result.format,
                                "mock": result.mock,
                            },
                        )
                    except Exception as exc:  # pragma: no cover - external TTS failures are runtime dependent.
                        message = (
                            exc.user_message
                            if isinstance(exc, TtsProviderError)
                            else "TTS 分段合成失败，已保留文字回答。"
                        )
                        yield _sse(
                            "tts_error",
                            {
                                "index": job["index"],
                                "text": job["text"],
                                "message": message,
                            },
                        )
                if not block or not tts_jobs or all(job["emitted"] for job in tts_jobs):
                    break
                if not emitted_any:
                    sleep(0.05)

        try:
            screen_response = _safe_screen_control_response(request, message_id=message_id)
            if screen_response is not None:
                response = screen_response
                yield _sse("dora_delta", {"text": response.speak_text})
                metrics_mode = ""
            else:
                metrics_mode = _ask_metrics_mode()
            metrics_response = None
            if metrics_mode == "excel":
                metrics_response = _safe_ask_metrics_response(request, message_id=message_id)

            if metrics_response is not None:
                response = metrics_response
                yield _sse("dora_delta", {"text": response.speak_text})
            elif metrics_mode == "auto":
                response = _chat_response(request).model_copy(update={"message_id": message_id})
                if response.type in {"answer", "screen_control"}:
                    yield _sse("dora_delta", {"text": response.speak_text})
            elif (knowledge_response := _safe_knowledge_response(request, message_id=message_id)) is not None:
                response = knowledge_response
                if response.type in {"answer", "screen_control"}:
                    yield _sse("dora_delta", {"text": response.speak_text})
            elif settings.enable_mock_dora:
                response = _with_message_id(mock_dora.respond(request), message_id)
            else:
                for event in dora_client.stream_sse_chat(request, message_id=message_id):
                    sse_events.append(event)
                    for chunk in _extract_ai_message_chunks(event):
                        delta = speak_extractor.feed(chunk)
                        if delta:
                            yield _sse("dora_delta", {"text": delta})
                            for segment in segmenter.add(delta):
                                schedule_tts(segment)
                    yield from emit_ready_jobs()

                raw_output = dora_client._collect_sse_output(sse_events)
                response = normalize_dora_output(
                    raw_output=raw_output,
                    request=request,
                    action_service=action_service,
                    message_id=message_id,
                )
        except DoraClientError as exc:
            logger.warning("Dora stream failed with code %s", exc.code)
            if settings.demo_stable_mode:
                response = _demo_stable_response(request, message_id=message_id, cause_code=exc.code)
                if response.type in {"answer", "screen_control"}:
                    yield _sse("dora_delta", {"text": response.speak_text})
            else:
                response = dora_error_response(
                    request=request,
                    message_id=message_id,
                    code=exc.code,
                    speak_text=exc.user_message,
                    reason=exc.code,
                )
        except Exception:
            logger.exception("Chat stream failed unexpectedly")
            response = dora_error_response(
                request=request,
                message_id=message_id,
                code="CHAT_STREAM_ERROR",
                speak_text="服务临时不可用，已保留文字回答入口，请稍后重试。",
                reason="CHAT_STREAM_ERROR",
            )

        for segment in segmenter.flush():
            schedule_tts(segment)

        if scheduled_count == 0 and response.type in {"answer", "screen_control"}:
            for segment in segmenter.add(response.speak_text):
                schedule_tts(segment)
            for segment in segmenter.flush():
                schedule_tts(segment)

        screen_action = None
        if response.action is not None:
            screen_action = {"action_id": response.action.id, "success": None}

        _safe_log_chat(
            session_id=response.session_id,
            message_id=response.message_id,
            user_text=request.text,
            intent_type=response.type,
            dora_response=response,
            screen_action=screen_action,
            error=response.error.model_dump() if response.error else None,
            started_at=started_at,
        )

        yield _sse("answer", response.model_dump(mode="json", exclude_none=True))
        yield from emit_ready_jobs(block=True)
        yield _sse("end", {"ok": True})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ops_dependency_statuses() -> list[OpsDependencyStatus]:
    dependencies = [
        _database_dependency_status(),
        _screen_actions_dependency_status(),
        _dora_dependency_status(),
        _ragflow_dependency_status(),
        _asr_dependency_status(),
        _tts_dependency_status(),
        _fvs_dependency_status(),
    ]
    return dependencies


def _database_dependency_status() -> OpsDependencyStatus:
    started_at = perf_counter()
    ok = session_logs.is_available()
    return _dependency_status(
        name="session_log",
        label="SQLite 会话日志",
        status="ok" if ok else "error",
        latency_ms=int((perf_counter() - started_at) * 1000),
        message="sessions.db 可读写" if ok else "sessions.db 不可访问",
        details={"path_configured": bool(settings.sqlite_path)},
    )


def _screen_actions_dependency_status() -> OpsDependencyStatus:
    started_at = perf_counter()
    try:
        actions_count = len(action_service.list_actions())
        return _dependency_status(
            name="screen_actions",
            label="大屏动作白名单",
            status="ok" if actions_count > 0 else "warning",
            latency_ms=int((perf_counter() - started_at) * 1000),
            message=f"已加载 {actions_count} 个 action_id",
            details={"action_count": actions_count},
        )
    except Exception:
        logger.warning("Ops screen actions check failed", exc_info=True)
        return _dependency_status(
            name="screen_actions",
            label="大屏动作白名单",
            status="error",
            latency_ms=int((perf_counter() - started_at) * 1000),
            message="动作白名单读取失败",
        )


def _dora_dependency_status() -> OpsDependencyStatus:
    if settings.enable_mock_dora:
        return _dependency_status(
            name="dora",
            label="Dora Agent",
            status="ok",
            message="Mock Dora 已启用",
            details={"mode": "mock"},
        )
    if not settings.dora_base_url.strip():
        return _dependency_status(
            name="dora",
            label="Dora Agent",
            status="error",
            message="未配置 Dora 地址",
            details={"mode": "real"},
        )
    if not settings.dora_api_key.strip():
        return _dependency_status(
            name="dora",
            label="Dora Agent",
            status="error",
            message="未配置 Dora API Key",
            details={"mode": "real"},
        )

    status, latency_ms, message = _probe_http(
        _join_url(settings.dora_base_url, "/external/api/openclaw/agents"),
        headers={"Authorization": "Bearer ***"},
        actual_headers={"Authorization": f"Bearer {settings.dora_api_key}"},
        ok_statuses={200},
    )
    return _dependency_status(
        name="dora",
        label="Dora Agent",
        status=status,
        latency_ms=latency_ms,
        message=message,
        details={
            "mode": "real",
            "agent_configured": bool(settings.dora_agent_id or settings.dora_agent_name),
            "channel_type": settings.dora_channel_type,
        },
    )


def _ragflow_dependency_status() -> OpsDependencyStatus:
    if settings.ragflow_base_url.strip():
        status, latency_ms, message = _probe_http(
            _join_url(settings.ragflow_base_url, "/api/v1/system/healthz"),
            ok_statuses={200},
        )
        return _dependency_status(
            name="ragflow",
            label="RAGFlow",
            status=status,
            latency_ms=latency_ms,
            message=message,
            details={"health_endpoint": "base_url", "mcp_configured": bool(settings.ragflow_mcp_url)},
        )
    if settings.ragflow_mcp_url.strip():
        status, latency_ms, message = _probe_http(
            settings.ragflow_mcp_url,
            headers={"Accept": "application/json, text/event-stream"},
            ok_statuses={200, 202, 406},
        )
        return _dependency_status(
            name="ragflow",
            label="RAGFlow",
            status=status,
            latency_ms=latency_ms,
            message=message,
            details={"health_endpoint": "mcp"},
        )
    return _dependency_status(
        name="ragflow",
        label="RAGFlow",
        status="warning",
        message="未配置 RAGFlow 地址",
        details={"mcp_configured": False},
    )


def _asr_dependency_status() -> OpsDependencyStatus:
    if settings.enable_mock_asr:
        return _dependency_status(
            name="asr",
            label="ASR",
            status="ok",
            message="Mock ASR 已启用",
            details={"mode": "mock", "provider": settings.asr_provider},
        )
    if not settings.asr_api_key.strip():
        return _dependency_status(
            name="asr",
            label="ASR",
            status="error",
            message="未配置 ASR API Key",
            details={"mode": "real", "provider": settings.asr_provider},
        )
    return _dependency_status(
        name="asr",
        label="ASR",
        status="ok",
        message="真实 ASR 配置已就绪",
        details={"mode": "real", "provider": settings.asr_provider, "model": settings.asr_model},
    )


def _tts_dependency_status() -> OpsDependencyStatus:
    if settings.enable_mock_tts:
        return _dependency_status(
            name="tts",
            label="TTS",
            status="ok",
            message="Mock TTS 已启用",
            details={"mode": "mock", "provider": settings.tts_provider},
        )
    if not settings.tts_api_key.strip():
        return _dependency_status(
            name="tts",
            label="TTS",
            status="error",
            message="未配置 TTS API Key",
            details={"mode": "real", "provider": settings.tts_provider},
        )
    return _dependency_status(
        name="tts",
        label="TTS",
        status="ok",
        message="真实 TTS 配置已就绪",
        details={
            "mode": "real",
            "provider": settings.tts_provider,
            "model": settings.tts_model,
            "streaming_enabled": settings.tts_streaming_enabled,
            "streaming_format": settings.tts_streaming_audio_format,
        },
    )


def _fvs_dependency_status() -> OpsDependencyStatus:
    if settings.enable_mock_fvs:
        return _dependency_status(
            name="fvs",
            label="FVS",
            status="ok",
            message="Mock FVS 已启用",
            details={"mode": "mock"},
        )
    if not settings.fvs_url.strip():
        return _dependency_status(
            name="fvs",
            label="FVS",
            status="warning",
            message="未配置 FVS iframe 地址",
            details={"mode": settings.fvs_integration_mode},
        )
    if settings.fvs_url.startswith(("http://", "https://")):
        status, latency_ms, message = _probe_http(settings.fvs_url, ok_statuses={200, 204, 301, 302})
        return _dependency_status(
            name="fvs",
            label="FVS",
            status=status,
            latency_ms=latency_ms,
            message=message,
            details={"mode": settings.fvs_integration_mode},
        )
    return _dependency_status(
        name="fvs",
        label="FVS",
        status="warning",
        message="FVS 使用相对路径，需由前端同源代理验证",
        details={"mode": settings.fvs_integration_mode, "relative_url": True},
    )


def _probe_http(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    actual_headers: dict[str, str] | None = None,
    ok_statuses: set[int],
) -> tuple[str, int | None, str]:
    request_headers = actual_headers if actual_headers is not None else headers
    started_at = perf_counter()
    try:
        with httpx.Client(timeout=2.5, follow_redirects=True) as client:
            response = client.get(url, headers=request_headers)
        latency_ms = int((perf_counter() - started_at) * 1000)
        if response.status_code in ok_statuses:
            return "ok", latency_ms, f"HTTP {response.status_code}"
        if response.status_code < 500:
            return "warning", latency_ms, f"HTTP {response.status_code}"
        return "error", latency_ms, f"HTTP {response.status_code}"
    except httpx.TimeoutException:
        return "error", int((perf_counter() - started_at) * 1000), "请求超时"
    except httpx.HTTPError:
        return "error", int((perf_counter() - started_at) * 1000), "请求失败"


def _dependency_status(
    *,
    name: str,
    label: str,
    status: str,
    message: str,
    latency_ms: int | None = None,
    details: dict | None = None,
) -> OpsDependencyStatus:
    return OpsDependencyStatus(
        name=name,
        label=label,
        status=status,
        latency_ms=latency_ms,
        message=message,
        checked_at=_now_iso(),
        details=details or {},
    )


def _overall_ops_status(dependencies: list[OpsDependencyStatus]) -> str:
    statuses = {dependency.status for dependency in dependencies}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    if "unknown" in statuses:
        return "unknown"
    return "ok"


def _ops_export_markdown(*, limit: int) -> str:
    dependencies = _ops_dependency_statuses()
    metrics = session_logs.metrics(recent_limit=20)
    sessions = session_logs.list_sessions(limit=limit)
    errors = session_logs.list_errors(limit=20)

    lines = [
        f"# {settings.project_name} 运维日志导出",
        "",
        f"- 导出时间: {_now_iso()}",
        f"- 应用: {settings.app_name} {settings.app_version}",
        f"- 客户: {settings.customer_name} ({settings.customer_id})",
        f"- 总体状态: {_overall_ops_status(dependencies)}",
        "",
        "## 依赖状态",
        "",
        "| 依赖 | 状态 | 延迟 | 摘要 |",
        "| --- | --- | ---: | --- |",
    ]
    for dependency in dependencies:
        latency = "-" if dependency.latency_ms is None else f"{dependency.latency_ms} ms"
        lines.append(
            f"| {_md_escape(dependency.label)} | {dependency.status} | {latency} | "
            f"{_md_escape(dependency.message)} |"
        )

    lines.extend(
        [
            "",
            "## 耗时指标",
            "",
            f"- 日志事件数: {metrics['total_events']}",
            f"- 会话数: {metrics['total_sessions']}",
            f"- 错误事件数: {metrics['error_events']}",
            f"- 平均耗时: {_format_ms(metrics['avg_latency_ms'])}",
            f"- P50 耗时: {_format_ms(metrics['p50_latency_ms'])}",
            f"- P95 耗时: {_format_ms(metrics['p95_latency_ms'])}",
            f"- 最大耗时: {_format_ms(metrics['max_latency_ms'])}",
            "",
            "## 最近会话",
            "",
            "| 时间 | 会话 | 事件 | 最近意图 | 最近耗时 | 最近输入 |",
            "| --- | --- | ---: | --- | ---: | --- |",
        ]
    )
    for session in sessions:
        lines.append(
            f"| {_md_escape(session['last_message_at'])} | {_md_escape(session['session_id'])} | "
            f"{session['turns']} | {_md_escape(session['last_intent_type'])} | "
            f"{_format_ms(session.get('last_latency_ms'))} | {_md_escape(session.get('last_user_text') or '-')} |"
        )

    lines.extend(
        [
            "",
            "## 最近错误",
            "",
            "| 时间 | 会话 | 类型 | 代码 | 摘要 |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for error in errors:
        lines.append(
            f"| {_md_escape(error['created_at'])} | {_md_escape(error['session_id'])} | "
            f"{_md_escape(error['intent_type'])} | {_md_escape(error['code'])} | "
            f"{_md_escape(error['message'])} |"
        )
    if not errors:
        lines.append("| - | - | - | - | 暂无错误 |")

    lines.append("")
    return "\n".join(lines)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _now_iso() -> str:
    try:
        tz = ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
    return datetime.now(tz).isoformat(timespec="seconds")


def _format_ms(value: int | None) -> str:
    return "-" if value is None else f"{value} ms"


def _md_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _extract_ai_message_chunks(event) -> list[str]:
    if event.event != "messages":
        return []
    data = event.data.strip()
    if not data:
        return []
    try:
        decoded = json.loads(data)
    except ValueError:
        return []
    if not isinstance(decoded, list):
        return []

    chunks: list[str] = []
    for item in decoded:
        if not isinstance(item, dict):
            continue
        message_type = str(item.get("type") or "").lower()
        if message_type != "aimessagechunk":
            continue
        if item.get("tool_calls"):
            continue
        content = item.get("content")
        if isinstance(content, str) and content:
            chunks.append(content)
    return chunks


class _SpeakTextExtractor:
    def __init__(self) -> None:
        self.buffer = ""
        self.in_value = False
        self.finished = False
        self.scan_index = 0
        self.escape = False

    def feed(self, chunk: str) -> str:
        if self.finished:
            return ""
        self.buffer += chunk
        if not self.in_value:
            key_index = self.buffer.find('"speak_text"')
            if key_index < 0:
                return ""
            colon_index = self.buffer.find(":", key_index)
            if colon_index < 0:
                return ""
            quote_index = self.buffer.find('"', colon_index)
            if quote_index < 0:
                return ""
            self.in_value = True
            self.scan_index = quote_index + 1

        output: list[str] = []
        while self.scan_index < len(self.buffer):
            char = self.buffer[self.scan_index]
            self.scan_index += 1
            if self.escape:
                output.append(_decode_json_escape_char(char))
                self.escape = False
                continue
            if char == "\\":
                self.escape = True
                continue
            if char == '"':
                self.finished = True
                break
            output.append(char)
        return "".join(output)


def _decode_json_escape_char(char: str) -> str:
    return {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        '"': '"',
        "\\": "\\",
        "/": "/",
    }.get(char, char)


class _SpeechSegmenter:
    def __init__(self, *, min_chars: int = 10, max_chars: int = 30) -> None:
        self.pending = ""
        self.min_chars = min_chars
        self.max_chars = max_chars

    def add(self, text: str) -> list[str]:
        self.pending += text
        return self._pop_ready_segments(final=False)

    def flush(self) -> list[str]:
        return self._pop_ready_segments(final=True)

    def _pop_ready_segments(self, *, final: bool) -> list[str]:
        segments: list[str] = []
        while self.pending:
            split_at = self._find_sentence_boundary()
            if split_at is None and len(self.pending) >= self.max_chars:
                split_at = self._find_soft_boundary() or self.max_chars
            if split_at is None:
                break
            segment = self.pending[:split_at].strip()
            self.pending = self.pending[split_at:].lstrip()
            if segment:
                segments.append(segment)

        if final and self.pending.strip():
            segments.append(self.pending.strip())
            self.pending = ""
        return segments

    def _find_sentence_boundary(self) -> int | None:
        for index, char in enumerate(self.pending):
            if index + 1 < self.min_chars:
                continue
            if char in "。！？!?；;：:":
                return index + 1
        return None

    def _find_soft_boundary(self) -> int | None:
        limit = min(len(self.pending), self.max_chars)
        for index in range(limit - 1, self.min_chars - 1, -1):
            if self.pending[index] in "，,、 ":
                return index + 1
        return None


@app.get("/api/screen/actions", response_model=ScreenActionsResponse)
def list_screen_actions() -> ScreenActionsResponse:
    return ScreenActionsResponse(actions=action_service.list_actions())


@app.post("/api/screen/execute", response_model=ScreenExecuteResponse)
def execute_screen_action(request: ScreenExecuteRequest, fastapi_request: Request) -> ScreenExecuteResponse:
    started_at = perf_counter()
    response = action_service.execute(
        request.action_id,
        request_id=_request_id(fastapi_request),
        params=request.params,
        target=request.target,
    )
    _safe_log_chat(
        session_id=request.session_id,
        message_id=f"screen-{uuid4().hex[:12]}",
        user_text="",
        intent_type="screen_execute",
        dora_response={},
        screen_action={
            "action_id": response.action_id,
            "success": response.success,
            "target": response.target,
            "provider": response.provider,
            "validation_status": response.validation.get("status") if response.validation else None,
            "rejection_reason": response.rejection_reason,
            "authorized_action": response.authorized_action.model_dump(mode="json")
            if response.authorized_action
            else None,
        },
        error=response.error.model_dump() if response.error else None,
        started_at=started_at,
    )
    return response


def _reload_runtime_services() -> dict[str, object]:
    global settings
    global config_override_service
    global action_service
    global screen_resolver
    global mock_dora
    global wake_words
    global ask_metrics
    global knowledge_service
    global asr_provider
    global tts_provider
    global dora_client

    get_settings.cache_clear()
    settings = get_settings()
    logging.getLogger().setLevel(settings.log_level)
    config_override_service = ConfigOverrideService(settings.config_overrides_dir)
    action_service = ScreenActionService(
        settings.action_whitelist_path,
        overrides=config_override_service.screen_action_overrides(),
    )
    screen_resolver = ScreenControlResolver(action_service)
    mock_dora = MockDoraService(settings.demo_cases_path, action_service)
    wake_words = WakeWordService(settings.wake_words_path)
    ask_metrics = AskMetricsService(settings.ask_metrics_data_dir, settings.ask_metrics_config_path)
    knowledge_service = build_knowledge_service(settings)
    asr_provider = build_asr_provider(
        enable_mock=settings.enable_mock_asr,
        provider_name=settings.asr_provider,
        api_key=settings.asr_api_key,
        model=settings.asr_model,
        ws_url=settings.asr_ws_url,
        audio_format=settings.asr_audio_format,
        sample_rate=settings.asr_sample_rate,
        timeout_seconds=settings.asr_timeout_seconds,
    )
    tts_provider = build_tts_provider(
        enable_mock=settings.enable_mock_tts,
        provider_name=settings.tts_provider,
        cache_dir=settings.tts_cache_dir,
        default_voice=settings.tts_voice,
        api_key=settings.tts_api_key,
        model=settings.tts_model,
        ws_url=settings.tts_ws_url,
        default_format=settings.tts_audio_format,
        sample_rate=settings.tts_sample_rate,
        timeout_seconds=settings.tts_timeout_seconds,
    )
    dora_client = DoraClient(
        base_url=settings.dora_base_url,
        api_key=settings.dora_api_key,
        agent_id=settings.dora_agent_id,
        agent_name=settings.dora_agent_name,
        channel_type=settings.dora_channel_type,
        timeout_seconds=settings.dora_timeout_seconds,
    )
    return {
        "customer_id": settings.customer_id,
        "project_name": settings.project_name,
        "ask_metrics_mode": settings.ask_metrics_mode,
        "knowledge_mode": settings.knowledge_mode,
        "action_count": len(action_service.list_actions()),
        "override_path": config_override_service.metadata()["path"],
    }


def _config_access_info() -> dict[str, object]:
    requires_token = bool(settings.config_admin_token.strip())
    return {
        "requires_token": requires_token,
        "token_header": "X-Config-Admin-Token",
        "operator_header": "X-Config-Operator",
        "local_origin_without_token": not requires_token,
        "write_scope": "non_sensitive_runtime_overrides",
    }


def _require_config_admin(request: Request, payload: ConfigOverridePayload) -> str:
    token = settings.config_admin_token.strip()
    supplied = request.headers.get("X-Config-Admin-Token", "")
    if token:
        if supplied != token:
            raise StarletteHTTPException(status_code=403, detail="Config admin token is required")
    elif not _is_local_config_request(request):
        raise StarletteHTTPException(status_code=403, detail="Config writes require localhost access or CONFIG_ADMIN_TOKEN")
    operator = request.headers.get("X-Config-Operator") or payload.operator or "local-admin"
    return _safe_operator(operator)


def _is_local_config_request(request: Request) -> bool:
    host = _hostname(request.headers.get("host", ""))
    origin = request.headers.get("origin")
    origin_host = _hostname(urlsplit(origin).netloc if origin else "")
    allowed = {"", "localhost", "127.0.0.1", "::1", "testserver"}
    if host not in allowed:
        return False
    return not origin_host or origin_host in allowed


def _hostname(value: str) -> str:
    host = value.strip().lower()
    if not host:
        return ""
    if host.startswith("[") and "]" in host:
        return host[1 : host.index("]")]
    if ":" in host:
        host = host.split(":", 1)[0]
    return host


def _safe_operator(value: str) -> str:
    cleaned = "".join(char for char in str(value).strip() if char.isalnum() or char in "._-@")
    return cleaned[:80] or "local-admin"


def _config_reason(payload: ConfigOverridePayload) -> str:
    reason = str(payload.reason or "").strip()
    return reason[:200]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", uuid4().hex)


def _safe_log_chat(**kwargs) -> None:
    try:
        session_logs.log_chat(**kwargs)
    except Exception as exc:  # pragma: no cover - logging must not break the demo path.
        logger.warning("Failed to write session log: %s", exc)


def _audio_media_type(suffix: str) -> str:
    return {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".pcm": "audio/L16",
        ".opus": "audio/opus",
    }.get(suffix.lower(), "application/octet-stream")
