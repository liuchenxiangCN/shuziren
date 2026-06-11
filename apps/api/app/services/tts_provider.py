import asyncio
import json
import math
import struct
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator, Protocol
from uuid import uuid4

import websockets


class TtsProviderError(Exception):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class TtsSynthesis:
    audio_id: str
    audio_path: Path
    audio_url: str
    duration_ms: int
    provider: str
    voice: str
    format: str
    mock: bool


@dataclass(frozen=True)
class TtsAudioChunk:
    index: int
    audio: bytes
    provider: str
    voice: str
    format: str
    mime_type: str
    sample_rate: int
    mock: bool


class TtsProvider(Protocol):
    provider_name: str
    is_mock: bool

    def synthesize(self, *, text: str, voice: str | None, audio_format: str | None) -> TtsSynthesis:
        ...

    def stream_synthesize(
        self, *, text: str, voice: str | None, audio_format: str | None
    ) -> AsyncIterator[TtsAudioChunk]:
        ...

    def get_audio_path(self, audio_id: str) -> Path | None:
        ...


class MockTtsProvider:
    provider_name = "mock"
    is_mock = True

    def __init__(self, cache_dir: str | Path, default_voice: str) -> None:
        self.cache_dir = Path(cache_dir)
        self.default_voice = default_voice

    def synthesize(self, *, text: str, voice: str | None, audio_format: str | None) -> TtsSynthesis:
        started_at = perf_counter()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        selected_voice = (voice or self.default_voice).strip() or self.default_voice
        duration_ms = _estimate_duration_ms(text)
        audio_id = f"tts-{uuid4().hex[:16]}.wav"
        audio_path = self.cache_dir / audio_id
        audio_path.write_bytes(_build_mock_wav(text=text, duration_ms=duration_ms))
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return TtsSynthesis(
            audio_id=audio_id,
            audio_path=audio_path,
            audio_url=f"/api/tts/audio/{audio_id}",
            duration_ms=max(duration_ms, elapsed_ms),
            provider=self.provider_name,
            voice=selected_voice,
            format="wav",
            mock=self.is_mock,
        )

    async def stream_synthesize(
        self, *, text: str, voice: str | None, audio_format: str | None
    ) -> AsyncIterator[TtsAudioChunk]:
        selected_voice = (voice or self.default_voice).strip() or self.default_voice
        duration_ms = _estimate_duration_ms(text)
        audio = _build_mock_pcm(text=text, duration_ms=duration_ms)
        bytes_per_chunk = 16_000 * 2 // 5
        for index, offset in enumerate(range(0, len(audio), bytes_per_chunk)):
            await asyncio.sleep(0.02)
            yield TtsAudioChunk(
                index=index,
                audio=audio[offset : offset + bytes_per_chunk],
                provider=self.provider_name,
                voice=selected_voice,
                format="pcm",
                mime_type="audio/L16",
                sample_rate=16_000,
                mock=self.is_mock,
            )

    def get_audio_path(self, audio_id: str) -> Path | None:
        if not _is_safe_audio_id(audio_id):
            return None
        audio_path = self.cache_dir / audio_id
        if not audio_path.exists():
            return None
        return audio_path


class UnsupportedTtsProvider:
    is_mock = False

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def synthesize(self, *, text: str, voice: str | None, audio_format: str | None) -> TtsSynthesis:
        raise TtsProviderError(
            code="TTS_PROVIDER_NOT_CONFIGURED",
            user_message="TTS 服务尚未配置真实供应商，请先使用 Mock TTS。",
        )

    async def stream_synthesize(
        self, *, text: str, voice: str | None, audio_format: str | None
    ) -> AsyncIterator[TtsAudioChunk]:
        raise TtsProviderError(
            code="TTS_PROVIDER_NOT_CONFIGURED",
            user_message="TTS 服务尚未配置真实供应商，请先使用 Mock TTS。",
        )
        yield  # pragma: no cover

    def get_audio_path(self, audio_id: str) -> Path | None:
        return None


class AliyunCosyVoiceTtsProvider:
    provider_name = "aliyun"
    is_mock = False

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        ws_url: str,
        cache_dir: str | Path,
        default_voice: str,
        default_format: str,
        sample_rate: int,
        timeout_seconds: int,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.ws_url = ws_url
        self.cache_dir = Path(cache_dir)
        self.default_voice = default_voice
        self.default_format = default_format
        self.sample_rate = sample_rate
        self.timeout_seconds = timeout_seconds

    def synthesize(self, *, text: str, voice: str | None, audio_format: str | None) -> TtsSynthesis:
        if not self.api_key:
            raise TtsProviderError(
                code="TTS_API_KEY_MISSING",
                user_message="TTS API Key 未配置，请检查本地 .env。",
            )

        started_at = perf_counter()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        selected_voice = (voice or self.default_voice).strip() or self.default_voice
        selected_format = _normalize_audio_format(audio_format or self.default_format)
        if selected_format not in {"mp3", "wav", "pcm", "opus"}:
            selected_format = self.default_format

        audio_bytes = asyncio.run(
            _run_cosyvoice_tts(
                api_key=self.api_key,
                ws_url=self.ws_url,
                model=self.model,
                text=text,
                voice=selected_voice,
                audio_format=selected_format,
                sample_rate=self.sample_rate,
                timeout_seconds=self.timeout_seconds,
            )
        )
        audio_id = f"tts-{uuid4().hex[:16]}.{selected_format}"
        audio_path = self.cache_dir / audio_id
        audio_path.write_bytes(audio_bytes)
        return TtsSynthesis(
            audio_id=audio_id,
            audio_path=audio_path,
            audio_url=f"/api/tts/audio/{audio_id}",
            duration_ms=max(1, int((perf_counter() - started_at) * 1000)),
            provider=self.provider_name,
            voice=selected_voice,
            format=selected_format,
            mock=self.is_mock,
        )

    async def stream_synthesize(
        self, *, text: str, voice: str | None, audio_format: str | None
    ) -> AsyncIterator[TtsAudioChunk]:
        if not self.api_key:
            raise TtsProviderError(
                code="TTS_API_KEY_MISSING",
                user_message="TTS API Key 未配置，请检查本地 .env。",
            )

        selected_voice = (voice or self.default_voice).strip() or self.default_voice
        selected_format = _normalize_audio_format(audio_format or "pcm")
        if selected_format not in {"mp3", "wav", "pcm", "opus"}:
            selected_format = "pcm"

        async for chunk in _stream_cosyvoice_tts(
            api_key=self.api_key,
            ws_url=self.ws_url,
            model=self.model,
            text=text,
            voice=selected_voice,
            audio_format=selected_format,
            sample_rate=self.sample_rate,
            timeout_seconds=self.timeout_seconds,
        ):
            yield TtsAudioChunk(
                index=chunk.index,
                audio=chunk.audio,
                provider=self.provider_name,
                voice=selected_voice,
                format=selected_format,
                mime_type=_audio_mime_type(selected_format),
                sample_rate=self.sample_rate,
                mock=self.is_mock,
            )

    def get_audio_path(self, audio_id: str) -> Path | None:
        if not _is_safe_audio_id(audio_id):
            return None
        audio_path = self.cache_dir / audio_id
        if not audio_path.exists():
            return None
        return audio_path


def build_tts_provider(
    *,
    enable_mock: bool,
    provider_name: str,
    cache_dir: str | Path,
    default_voice: str,
    api_key: str = "",
    model: str = "cosyvoice-v3-flash",
    ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/inference",
    default_format: str = "mp3",
    sample_rate: int = 22050,
    timeout_seconds: int = 30,
) -> TtsProvider:
    if enable_mock:
        return MockTtsProvider(cache_dir=cache_dir, default_voice=default_voice)
    if provider_name.lower() in {"aliyun", "dashscope", "bailian"}:
        return AliyunCosyVoiceTtsProvider(
            api_key=api_key,
            model=model,
            ws_url=ws_url,
            cache_dir=cache_dir,
            default_voice=default_voice,
            default_format=default_format,
            sample_rate=sample_rate,
            timeout_seconds=timeout_seconds,
        )
    return UnsupportedTtsProvider(provider_name=provider_name)


def _estimate_duration_ms(text: str) -> int:
    return min(5200, max(900, len(text.strip()) * 95))


def _build_mock_wav(*, text: str, duration_ms: int) -> bytes:
    sample_rate = 16_000
    total_frames = int(sample_rate * duration_ms / 1000)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        seed = sum(ord(char) for char in text) % 97
        frames = bytearray()
        for index in range(total_frames):
            progress = index / max(1, total_frames)
            envelope = min(1.0, progress * 8) * min(1.0, (1 - progress) * 8)
            frequency = 180 + seed + 35 * math.sin(progress * math.tau * 3)
            sample = int(0.22 * envelope * 32767 * math.sin(math.tau * frequency * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        wav_file.writeframes(bytes(frames))
    return buffer.getvalue()


def _build_mock_pcm(*, text: str, duration_ms: int) -> bytes:
    sample_rate = 16_000
    total_frames = int(sample_rate * duration_ms / 1000)
    seed = sum(ord(char) for char in text) % 97
    frames = bytearray()
    for index in range(total_frames):
        progress = index / max(1, total_frames)
        envelope = min(1.0, progress * 8) * min(1.0, (1 - progress) * 8)
        frequency = 180 + seed + 35 * math.sin(progress * math.tau * 3)
        sample = int(0.22 * envelope * 32767 * math.sin(math.tau * frequency * index / sample_rate))
        frames.extend(struct.pack("<h", sample))
    return bytes(frames)


def _is_safe_audio_id(audio_id: str) -> bool:
    allowed_suffixes = (".wav", ".mp3", ".pcm", ".opus")
    if not audio_id.startswith("tts-") or not audio_id.endswith(allowed_suffixes):
        return False
    return all(char.isalnum() or char in {"-", "."} for char in audio_id)


def _normalize_audio_format(audio_format: str) -> str:
    value = audio_format.split(";")[0].strip().lower()
    aliases = {
        "audio/wav": "wav",
        "audio/wave": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/opus": "opus",
    }
    return aliases.get(value, value)


async def _run_cosyvoice_tts(
    *,
    api_key: str,
    ws_url: str,
    model: str,
    text: str,
    voice: str,
    audio_format: str,
    sample_rate: int,
    timeout_seconds: int,
) -> bytes:
    audio_parts: list[bytes] = []
    async for chunk in _stream_cosyvoice_tts(
        api_key=api_key,
        ws_url=ws_url,
        model=model,
        text=text,
        voice=voice,
        audio_format=audio_format,
        sample_rate=sample_rate,
        timeout_seconds=timeout_seconds,
    ):
        audio_parts.append(chunk.audio)

    audio_bytes = b"".join(audio_parts)
    if not audio_bytes:
        raise TtsProviderError(
            code="TTS_EMPTY_AUDIO",
            user_message="TTS 未返回音频，请稍后重试。",
        )
    return audio_bytes


async def _stream_cosyvoice_tts(
    *,
    api_key: str,
    ws_url: str,
    model: str,
    text: str,
    voice: str,
    audio_format: str,
    sample_rate: int,
    timeout_seconds: int,
) -> AsyncIterator[TtsAudioChunk]:
    task_id = str(uuid4())
    headers = {
        "Authorization": f"Bearer {api_key}",
        "user-agent": "zt-digital-human-api",
    }
    run_task = {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "tts",
            "function": "SpeechSynthesizer",
            "model": model,
            "parameters": {
                "text_type": "PlainText",
                "voice": voice,
                "format": audio_format,
                "sample_rate": sample_rate,
                "volume": 50,
                "rate": 1.0,
                "pitch": 1.0,
                "enable_ssml": False,
            },
            "input": {},
        },
    }
    continue_task = {
        "header": {
            "action": "continue-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {"text": text}},
    }
    finish_task = {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {}},
    }

    chunk_index = 0
    try:
        async with asyncio.timeout(timeout_seconds):
            async with websockets.connect(ws_url, additional_headers=headers) as websocket:
                await websocket.send(json.dumps(run_task, ensure_ascii=False))
                await _wait_for_tts_event(websocket, "task-started")
                await websocket.send(json.dumps(continue_task, ensure_ascii=False))
                await websocket.send(json.dumps(finish_task, ensure_ascii=False))

                async for message in websocket:
                    if isinstance(message, bytes):
                        yield TtsAudioChunk(
                            index=chunk_index,
                            audio=message,
                            provider="aliyun",
                            voice=voice,
                            format=audio_format,
                            mime_type=_audio_mime_type(audio_format),
                            sample_rate=sample_rate,
                            mock=False,
                        )
                        chunk_index += 1
                        continue
                    payload = json.loads(message)
                    header = payload.get("header", {})
                    event = header.get("event")
                    if event == "task-failed":
                        raise TtsProviderError(
                            code=str(header.get("error_code") or "TTS_TASK_FAILED"),
                            user_message="TTS 合成失败，请检查音色和百炼配置。",
                        )
                    if event == "task-finished":
                        break
    except TtsProviderError:
        raise
    except TimeoutError as exc:
        raise TtsProviderError(
            code="TTS_REQUEST_TIMEOUT",
            user_message="TTS 合成超时，请稍后重试。",
        ) from exc
    except Exception as exc:
        raise TtsProviderError(
            code="TTS_REQUEST_ERROR",
            user_message="TTS 服务暂时不可用，请稍后再试。",
        ) from exc

    if chunk_index == 0:
        raise TtsProviderError(
            code="TTS_EMPTY_AUDIO",
            user_message="TTS 未返回音频，请稍后重试。",
        )


async def _wait_for_tts_event(websocket, expected_event: str) -> None:
    async for message in websocket:
        if isinstance(message, bytes):
            continue
        payload = json.loads(message)
        header = payload.get("header", {})
        event = header.get("event")
        if event == expected_event:
            return
        if event == "task-failed":
            raise TtsProviderError(
                code=str(header.get("error_code") or "TTS_TASK_FAILED"),
                user_message="TTS 任务启动失败，请检查百炼配置。",
            )


def _audio_mime_type(audio_format: str) -> str:
    return {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "pcm": "audio/L16",
        "opus": "audio/opus",
    }.get(audio_format.lower(), "application/octet-stream")
