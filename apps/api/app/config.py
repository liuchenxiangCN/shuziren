from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_project_root() -> Path:
    current = Path(__file__).resolve()
    candidates = [Path.cwd(), *current.parents]
    for candidate in candidates:
        if (candidate / "config").exists():
            return candidate
    return Path.cwd()


PROJECT_ROOT = _resolve_project_root()


class Settings(BaseSettings):
    app_name: str = "zt-digital-human-api"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    action_whitelist_path: str = Field(
        default=str(PROJECT_ROOT / "config" / "screen-actions.yaml")
    )
    demo_cases_path: str = Field(default=str(PROJECT_ROOT / "config" / "demo-cases.yaml"))
    wake_words_path: str = Field(default=str(PROJECT_ROOT / "config" / "wake-words.yaml"))
    ask_metrics_data_dir: str = Field(
        default=str(PROJECT_ROOT / "docs" / "demo_data" / "ask_metrics")
    )
    ask_metrics_config_path: str = Field(
        default=str(PROJECT_ROOT / "config" / "ask-metrics.yaml")
    )
    sqlite_path: str = Field(default=str(PROJECT_ROOT / "data" / "sessions.db"))
    tts_cache_dir: str = Field(default=str(PROJECT_ROOT / "data" / "tts-cache"))

    dora_base_url: str = ""
    dora_api_key: str = ""
    dora_agent_id: str = ""
    dora_agent_name: str = ""
    dora_channel_type: str = "feishu"
    dora_chat_mode: str = "sse"
    dora_timeout_seconds: int = 60

    asr_provider: str = "aliyun"
    asr_api_key: str = ""
    asr_model: str = "fun-asr-realtime"
    asr_region: str = "cn-beijing"
    asr_ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    asr_audio_format: str = "wav"
    asr_sample_rate: int = 16000
    asr_timeout_seconds: int = 30

    tts_provider: str = "aliyun"
    tts_api_key: str = ""
    tts_model: str = "cosyvoice-v3-flash"
    tts_voice: str = "longanyang"
    tts_audio_format: str = "mp3"
    tts_ws_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"
    tts_sample_rate: int = 22050
    tts_timeout_seconds: int = 30

    enable_mock_dora: bool = True
    enable_mock_asr: bool = True
    enable_mock_tts: bool = True
    enable_mock_fvs: bool = True

    cors_origins: list[str] = [
        "http://localhost:18000",
        "http://127.0.0.1:18000",
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
