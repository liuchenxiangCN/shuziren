import json
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from time import sleep
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.models import (
    AsrTranscribeRequest,
    AsrTranscribeResponse,
    ChatRequest,
    ChatResponse,
    ErrorDetail,
    HealthResponse,
    ScreenActionsResponse,
    ScreenExecuteRequest,
    ScreenExecuteResponse,
    TtsSynthesizeRequest,
    TtsSynthesizeResponse,
    WakeConfigResponse,
)
from app.services.asr_provider import AsrProviderError, build_asr_provider
from app.services.ask_metrics import AskMetricsService
from app.services.dora_client import DoraClient, DoraClientError
from app.services.dora_normalizer import dora_error_response, normalize_dora_output
from app.services.mock_dora import MockDoraService
from app.services.screen_actions import ScreenActionService
from app.services.session_log import SessionLogStore
from app.services.tts_provider import TtsProviderError, build_tts_provider
from app.services.wake_words import WakeWordService


settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

action_service = ScreenActionService(settings.action_whitelist_path)
mock_dora = MockDoraService(settings.demo_cases_path, action_service)
wake_words = WakeWordService(settings.wake_words_path)
ask_metrics = AskMetricsService(settings.ask_metrics_data_dir, settings.ask_metrics_config_path)
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


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
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


@app.get("/api/tts/audio/{audio_id}")
def get_tts_audio(audio_id: str) -> FileResponse:
    audio_path = tts_provider.get_audio_path(audio_id)
    if audio_path is None:
        raise StarletteHTTPException(status_code=404, detail="TTS audio not found")
    return FileResponse(path=audio_path, media_type=_audio_media_type(audio_path.suffix), filename=audio_id)


def _chat_response(request: ChatRequest) -> ChatResponse:
    metrics_response = ask_metrics.respond(request)
    if metrics_response is not None:
        return metrics_response

    if settings.enable_mock_dora:
        return mock_dora.respond(request)

    message_id = f"msg-{uuid4().hex[:12]}"
    try:
        result = dora_client.sse_chat(request, message_id=message_id)
        return normalize_dora_output(
            raw_output=result.raw_output,
            request=request,
            action_service=action_service,
            message_id=result.message_id,
        )
    except DoraClientError as exc:
        logger.warning("Dora chat failed with code %s", exc.code)
        return dora_error_response(
            request=request,
            message_id=message_id,
            code=exc.code,
            speak_text=exc.user_message,
            reason=exc.code,
        )


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
                        yield _sse(
                            "tts_error",
                            {
                                "index": job["index"],
                                "text": job["text"],
                                "message": str(exc),
                            },
                        )
                if not block or not tts_jobs or all(job["emitted"] for job in tts_jobs):
                    break
                if not emitted_any:
                    sleep(0.05)

        try:
            metrics_response = ask_metrics.respond(request, message_id=message_id)
            if metrics_response is not None:
                response = metrics_response
                yield _sse("dora_delta", {"text": response.speak_text})
            elif settings.enable_mock_dora:
                response = mock_dora.respond(request)
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
            response = dora_error_response(
                request=request,
                message_id=message_id,
                code=exc.code,
                speak_text=exc.user_message,
                reason=exc.code,
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
        },
        error=response.error.model_dump() if response.error else None,
        started_at=started_at,
    )
    return response


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
