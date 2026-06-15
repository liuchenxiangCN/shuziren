import asyncio
import base64
import json
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol
from uuid import uuid4

import websockets


class AsrProviderError(Exception):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class AsrTranscription:
    text: str
    duration_ms: int
    provider: str
    mock: bool


class AsrProvider(Protocol):
    provider_name: str
    is_mock: bool

    def transcribe(
        self,
        *,
        mock_text: str | None,
        audio_base64: str | None,
        audio_format: str | None,
    ) -> AsrTranscription:
        ...


class MockAsrProvider:
    provider_name = "mock"
    is_mock = True
    _default_text = "请切换到组织建设页面"

    def transcribe(
        self,
        *,
        mock_text: str | None,
        audio_base64: str | None,
        audio_format: str | None,
    ) -> AsrTranscription:
        started_at = perf_counter()
        if audio_base64:
            _decode_audio(audio_base64)
        text = (mock_text or "").strip() or self._default_text
        return AsrTranscription(
            text=text,
            duration_ms=max(1, int((perf_counter() - started_at) * 1000)),
            provider=self.provider_name,
            mock=self.is_mock,
        )


class UnsupportedAsrProvider:
    is_mock = False

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def transcribe(
        self,
        *,
        mock_text: str | None,
        audio_base64: str | None,
        audio_format: str | None,
    ) -> AsrTranscription:
        raise AsrProviderError(
            code="ASR_PROVIDER_NOT_CONFIGURED",
            user_message="ASR 服务尚未配置真实供应商，请先使用 Mock ASR。",
        )


class AliyunFunAsrProvider:
    provider_name = "aliyun"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        ws_url: str,
        audio_format: str,
        sample_rate: int,
        timeout_seconds: int,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.ws_url = ws_url
        self.audio_format = audio_format
        self.sample_rate = sample_rate
        self.timeout_seconds = timeout_seconds

    def transcribe(
        self,
        *,
        mock_text: str | None,
        audio_base64: str | None,
        audio_format: str | None,
    ) -> AsrTranscription:
        if not self.api_key:
            raise AsrProviderError(
                code="ASR_API_KEY_MISSING",
                user_message="ASR API Key 未配置，请检查本地 .env。",
            )
        if not audio_base64:
            raise AsrProviderError(
                code="ASR_AUDIO_REQUIRED",
                user_message="请先录音，再发起真实 ASR 识别。",
            )

        started_at = perf_counter()
        audio_bytes = _decode_audio(audio_base64)
        selected_format = _normalize_audio_format(audio_format or self.audio_format)
        if selected_format == "webm":
            raise AsrProviderError(
                code="ASR_AUDIO_FORMAT_UNSUPPORTED",
                user_message="阿里云 Fun-ASR 不支持 WebM，请使用 WAV/PCM 录音格式。",
            )

        text = asyncio.run(
            _run_fun_asr(
                api_key=self.api_key,
                ws_url=self.ws_url,
                model=self.model,
                audio_bytes=audio_bytes,
                audio_format=selected_format,
                sample_rate=self.sample_rate,
                timeout_seconds=self.timeout_seconds,
            )
        )
        return AsrTranscription(
            text=text,
            duration_ms=max(1, int((perf_counter() - started_at) * 1000)),
            provider=self.provider_name,
            mock=self.is_mock,
        )


def build_asr_provider(
    *,
    enable_mock: bool,
    provider_name: str,
    api_key: str = "",
    model: str = "fun-asr-realtime",
    ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/inference",
    audio_format: str = "wav",
    sample_rate: int = 16000,
    timeout_seconds: int = 30,
) -> AsrProvider:
    if enable_mock:
        return MockAsrProvider()
    if provider_name.lower() in {"aliyun", "dashscope", "bailian"}:
        return AliyunFunAsrProvider(
            api_key=api_key,
            model=model,
            ws_url=ws_url,
            audio_format=audio_format,
            sample_rate=sample_rate,
            timeout_seconds=timeout_seconds,
        )
    return UnsupportedAsrProvider(provider_name=provider_name)


def _decode_audio(audio_base64: str) -> bytes:
    try:
        return base64.b64decode(audio_base64, validate=True)
    except Exception as exc:
        raise AsrProviderError(
            code="ASR_AUDIO_INVALID",
            user_message="音频数据格式不正确，请重新录制。",
        ) from exc


def _normalize_audio_format(audio_format: str) -> str:
    value = audio_format.split(";")[0].strip().lower()
    aliases = {
        "audio/wav": "wav",
        "audio/wave": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/aac": "aac",
        "audio/amr": "amr",
        "audio/ogg": "opus",
        "audio/webm": "webm",
    }
    return aliases.get(value, value)


async def _run_fun_asr(
    *,
    api_key: str,
    ws_url: str,
    model: str,
    audio_bytes: bytes,
    audio_format: str,
    sample_rate: int,
    timeout_seconds: int,
) -> str:
    task_id = str(uuid4())
    headers = {
        "Authorization": f"Bearer {api_key}",
        "user-agent": "configurable-digital-human-api",
    }
    run_task = {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": model,
            "parameters": {
                "format": audio_format,
                "sample_rate": sample_rate,
                "language_hints": ["zh"],
                "punctuation_prediction_enabled": True,
            },
            "input": {},
        },
    }
    finish_task = {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {}},
    }

    final_sentences: list[str] = []
    latest_text = ""
    try:
        async with asyncio.timeout(timeout_seconds):
            async with websockets.connect(ws_url, additional_headers=headers) as websocket:
                await websocket.send(json.dumps(run_task, ensure_ascii=False))
                await _wait_for_event(websocket, "task-started")

                for start in range(0, len(audio_bytes), 8 * 1024):
                    await websocket.send(audio_bytes[start : start + 8 * 1024])
                await websocket.send(json.dumps(finish_task, ensure_ascii=False))

                async for message in websocket:
                    if isinstance(message, bytes):
                        continue
                    payload = json.loads(message)
                    header = payload.get("header", {})
                    event = header.get("event")
                    if event == "result-generated":
                        sentence = payload.get("payload", {}).get("output", {}).get("sentence", {})
                        if sentence.get("heartbeat"):
                            continue
                        text = str(sentence.get("text") or "").strip()
                        if text:
                            latest_text = text
                        if text and sentence.get("sentence_end"):
                            final_sentences.append(text)
                    elif event == "task-failed":
                        raise AsrProviderError(
                            code=str(header.get("error_code") or "ASR_TASK_FAILED"),
                            user_message="ASR 识别失败，请检查音频和百炼配置。",
                        )
                    elif event == "task-finished":
                        break
    except AsrProviderError:
        raise
    except TimeoutError as exc:
        raise AsrProviderError(
            code="ASR_REQUEST_TIMEOUT",
            user_message="ASR 识别超时，请稍后重试。",
        ) from exc
    except Exception as exc:
        raise AsrProviderError(
            code="ASR_REQUEST_ERROR",
            user_message="ASR 服务暂时不可用，请稍后再试。",
        ) from exc

    text = "".join(final_sentences).strip() or latest_text
    if not text:
        raise AsrProviderError(
            code="ASR_EMPTY_RESULT",
            user_message="我没有听清楚，请您再说一遍。",
        )
    return text


async def _wait_for_event(websocket, expected_event: str) -> None:
    async for message in websocket:
        if isinstance(message, bytes):
            continue
        payload = json.loads(message)
        header = payload.get("header", {})
        event = header.get("event")
        if event == expected_event:
            return
        if event == "task-failed":
            raise AsrProviderError(
                code=str(header.get("error_code") or "ASR_TASK_FAILED"),
                user_message="ASR 任务启动失败，请检查百炼配置。",
            )
