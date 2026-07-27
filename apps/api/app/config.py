import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services.config_overrides import apply_settings_overrides
from app.services.yaml_loader import load_yaml_file


def _resolve_project_root() -> Path:
    current = Path(__file__).resolve()
    candidates = [Path.cwd(), *current.parents]
    for candidate in candidates:
        if (candidate / "config").exists():
            return candidate
    return Path.cwd()


PROJECT_ROOT = _resolve_project_root()


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "configurable-digital-human-api"
    app_version: str = "0.1.0"
    log_level: str = "INFO"
    project_id: str = "configurable-digital-human"
    project_name: str = "通用可配置数字人 POC"
    product_name: str = "可配置大屏对话数字人"
    customer_id: str = "default"
    customer_name: str = "默认客户"
    scenario_name: str = "通用大屏交互"
    assistant_name: str = "小智"
    customer_config_dir: str = ""
    demo_stable_mode: bool = False

    action_whitelist_path: str = Field(default=str(PROJECT_ROOT / "config" / "screen-actions.yaml"))
    demo_cases_path: str = Field(default=str(PROJECT_ROOT / "config" / "demo-cases.yaml"))
    wake_words_path: str = Field(default=str(PROJECT_ROOT / "config" / "wake-words.yaml"))
    ask_metrics_data_dir: str = Field(default=str(PROJECT_ROOT / "docs" / "demo_data" / "ask_metrics"))
    ask_metrics_config_path: str = Field(default=str(PROJECT_ROOT / "config" / "ask-metrics.yaml"))
    ask_metrics_mode: str = "excel"
    sqlite_path: str = Field(default=str(PROJECT_ROOT / "data" / "sessions.db"))
    session_log_retention_days: int = Field(default=3, ge=1, le=3650)
    tts_cache_dir: str = Field(default=str(PROJECT_ROOT / "data" / "tts-cache"))
    config_overrides_dir: str = Field(default=str(PROJECT_ROOT / "data" / "config-overrides"))
    config_admin_token: str = ""
    control_plane_db_path: str = Field(default=str(PROJECT_ROOT / "data" / "control-plane.db"))
    control_plane_backup_root: str = Field(default=str(PROJECT_ROOT / "data" / "control-plane-backups"))
    control_plane_root_key_b64: str = ""
    control_plane_preview_mode: bool = False
    control_plane_allowed_origins: list[str] = [
        "http://localhost:18000",
        "http://127.0.0.1:18000",
    ]

    dora_base_url: str = ""
    dora_api_key: str = ""
    dora_agent_id: str = ""
    dora_agent_name: str = ""
    dora_channel_type: str = "feishu"
    dora_chat_mode: str = "sse"
    dora_timeout_seconds: int = 60

    ragflow_base_url: str = ""
    ragflow_mcp_url: str = ""
    ragflow_api_key: str = ""
    knowledge_mode: str = "dora"
    knowledge_retrieval_transport: str = "api"
    knowledge_dataset_ids: str = ""
    knowledge_dataset_name: str = ""
    knowledge_page_size: int = 3
    knowledge_top_k: int = 16
    knowledge_similarity_threshold: float = 0.35
    knowledge_max_chunk_chars: int = 1200
    knowledge_timeout_seconds: int = 15
    knowledge_require_sources: bool = True
    knowledge_no_evidence_policy: str = "fallback"
    knowledge_fallback_text: str = "知识库未找到可靠依据，请补充资料后再试。"
    knowledge_summarizer_provider: str = "source_bound_extractive"
    knowledge_summarizer_profile: str = "source_bound_extractive"
    knowledge_max_answer_chars: int = 800

    fvs_integration_mode: str = "mock"
    fvs_url: str = ""
    fvs_target_origin: str = ""

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
    tts_streaming_enabled: bool = True
    tts_streaming_fallback: str = "segment"
    tts_streaming_audio_format: str = "pcm"
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

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore",
        case_sensitive=False,
        env_ignore_empty=True,
    )


@lru_cache
def get_settings() -> Settings:
    return apply_settings_overrides(_apply_customer_config(Settings()))


def _apply_customer_config(settings: Settings) -> Settings:
    customer_id = settings.customer_id.strip() or "default"
    customer_dir = _customer_config_dir(settings, customer_id)
    env_vars = _configured_env_vars()
    overrides: dict[str, Any] = {
        "customer_id": customer_id,
        "customer_config_dir": str(customer_dir),
    }

    runtime = _load_optional_yaml(customer_dir / "runtime.yaml")
    if runtime:
        project = runtime.get("project")
        if not isinstance(project, dict):
            project = {}
        for setting_name, env_key in (
            ("project_id", "PROJECT_ID"),
            ("project_name", "PROJECT_NAME"),
            ("product_name", "PRODUCT_NAME"),
            ("customer_name", "CUSTOMER_NAME"),
            ("scenario_name", "SCENARIO_NAME"),
            ("assistant_name", "ASSISTANT_NAME"),
        ):
            _overlay_value(
                overrides,
                env_vars,
                setting_name,
                env_key,
                project.get(setting_name, runtime.get(setting_name)),
            )
        _overlay_value(
            overrides,
            env_vars,
            "demo_stable_mode",
            "DEMO_STABLE_MODE",
            runtime.get("demo_stable_mode"),
            normalizer=_to_bool,
        )
        demo = runtime.get("demo")
        if isinstance(demo, dict):
            _overlay_value(
                overrides,
                env_vars,
                "demo_stable_mode",
                "DEMO_STABLE_MODE",
                demo.get("stable_mode"),
                normalizer=_to_bool,
            )
        _overlay_value(
            overrides,
            env_vars,
            "ask_metrics_mode",
            "ASK_METRICS_MODE",
            runtime.get("ask_metrics_mode"),
            normalizer=_normalize_ask_metrics_mode,
        )
        ask_metrics = runtime.get("ask_metrics")
        if isinstance(ask_metrics, dict):
            _overlay_value(
                overrides,
                env_vars,
                "ask_metrics_mode",
                "ASK_METRICS_MODE",
                ask_metrics.get("mode"),
                normalizer=_normalize_ask_metrics_mode,
            )
            _overlay_path(
                overrides,
                env_vars,
                "ask_metrics_data_dir",
                "ASK_METRICS_DATA_DIR",
                ask_metrics.get("data_dir"),
                customer_dir,
            )

    _overlay_customer_file(
        overrides,
        env_vars,
        "action_whitelist_path",
        "ACTION_WHITELIST_PATH",
        customer_dir / "screen-actions.yaml",
    )
    _overlay_customer_file(
        overrides,
        env_vars,
        "demo_cases_path",
        "DEMO_CASES_PATH",
        customer_dir / "demo-cases.yaml",
    )
    _overlay_customer_file(
        overrides,
        env_vars,
        "wake_words_path",
        "WAKE_WORDS_PATH",
        customer_dir / "wake-words.yaml",
    )
    _overlay_customer_file(
        overrides,
        env_vars,
        "ask_metrics_config_path",
        "ASK_METRICS_CONFIG_PATH",
        customer_dir / "ask-metrics.yaml",
    )

    ask_metrics_config = _load_optional_yaml(customer_dir / "ask-metrics.yaml")
    if ask_metrics_config:
        _overlay_value(
            overrides,
            env_vars,
            "ask_metrics_mode",
            "ASK_METRICS_MODE",
            ask_metrics_config.get("mode"),
            normalizer=_normalize_ask_metrics_mode,
        )
        _overlay_path(
            overrides,
            env_vars,
            "ask_metrics_data_dir",
            "ASK_METRICS_DATA_DIR",
            ask_metrics_config.get("data_dir"),
            customer_dir,
        )

    _overlay_dora_config(overrides, env_vars, customer_dir / "dora.yaml")
    _overlay_ragflow_config(overrides, env_vars, customer_dir / "ragflow.yaml")
    _overlay_voice_config(overrides, env_vars, customer_dir / "voice.yaml")
    _overlay_fvs_config(overrides, env_vars, customer_dir / "fvs.yaml")
    _overlay_env_alias(overrides, env_vars, "fvs_url", "VITE_FVS_URL")
    _overlay_env_alias(
        overrides,
        env_vars,
        "fvs_integration_mode",
        "VITE_FVS_INTEGRATION_MODE",
        normalizer=_normalize_fvs_mode,
    )
    _overlay_env_alias(overrides, env_vars, "fvs_target_origin", "VITE_FVS_TARGET_ORIGIN")

    return settings.model_copy(update=overrides)


def _customer_config_dir(settings: Settings, customer_id: str) -> Path:
    if settings.customer_config_dir.strip():
        return _resolve_config_path(settings.customer_config_dir, PROJECT_ROOT)
    return PROJECT_ROOT / "config" / "customers" / customer_id


def _configured_env_vars() -> dict[str, str]:
    values = {key.upper(): value for key, value in os.environ.items()}
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return values

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key:
            values.setdefault(key.upper(), value.strip().strip("'\""))
    return values


def _load_optional_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return load_yaml_file(path)


def _overlay_customer_file(
    overrides: dict[str, Any],
    env_vars: dict[str, str],
    setting_name: str,
    env_key: str,
    path: Path,
) -> None:
    if _has_env_override(env_vars, env_key, legacy_config_file=path.name) or not path.exists():
        return
    overrides[setting_name] = str(path)


def _overlay_dora_config(overrides: dict[str, Any], env_vars: dict[str, str], path: Path) -> None:
    data = _load_optional_yaml(path)
    if not data:
        return
    _overlay_value(overrides, env_vars, "dora_base_url", "DORA_BASE_URL", data.get("base_url"))
    _overlay_value(overrides, env_vars, "dora_agent_id", "DORA_AGENT_ID", data.get("agent_id"))
    _overlay_value(overrides, env_vars, "dora_agent_name", "DORA_AGENT_NAME", data.get("agent_name"))
    _overlay_value(
        overrides,
        env_vars,
        "dora_channel_type",
        "DORA_CHANNEL_TYPE",
        data.get("channel_type"),
    )
    _overlay_value(overrides, env_vars, "dora_chat_mode", "DORA_CHAT_MODE", data.get("chat_mode"))
    _overlay_value(
        overrides,
        env_vars,
        "dora_timeout_seconds",
        "DORA_TIMEOUT_SECONDS",
        data.get("timeout_seconds"),
        normalizer=_to_int,
    )


def _overlay_ragflow_config(overrides: dict[str, Any], env_vars: dict[str, str], path: Path) -> None:
    data = _load_optional_yaml(path)
    if not data:
        return
    _overlay_value(overrides, env_vars, "ragflow_base_url", "RAGFLOW_BASE_URL", data.get("base_url"))
    _overlay_value(overrides, env_vars, "ragflow_mcp_url", "RAGFLOW_MCP_URL", data.get("mcp_url"))
    _overlay_value(
        overrides,
        env_vars,
        "knowledge_dataset_name",
        "KNOWLEDGE_DATASET_NAME",
        data.get("dataset_name"),
    )
    _overlay_value(
        overrides,
        env_vars,
        "knowledge_dataset_ids",
        "KNOWLEDGE_DATASET_IDS",
        data.get("dataset_ids"),
        normalizer=_normalize_csv,
    )
    knowledge = data.get("knowledge")
    if isinstance(knowledge, dict):
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_mode",
            "KNOWLEDGE_MODE",
            knowledge.get("mode"),
            normalizer=_normalize_knowledge_mode,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_fallback_text",
            "KNOWLEDGE_FALLBACK_TEXT",
            knowledge.get("fallback_text"),
        )
    retrieval = data.get("retrieval")
    if isinstance(retrieval, dict):
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_retrieval_transport",
            "KNOWLEDGE_RETRIEVAL_TRANSPORT",
            retrieval.get("transport"),
            normalizer=_normalize_knowledge_transport,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_dataset_name",
            "KNOWLEDGE_DATASET_NAME",
            retrieval.get("dataset_name"),
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_dataset_ids",
            "KNOWLEDGE_DATASET_IDS",
            retrieval.get("dataset_ids"),
            normalizer=_normalize_csv,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_page_size",
            "KNOWLEDGE_PAGE_SIZE",
            retrieval.get("page_size"),
            normalizer=_to_int,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_top_k",
            "KNOWLEDGE_TOP_K",
            retrieval.get("top_k"),
            normalizer=_to_int,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_similarity_threshold",
            "KNOWLEDGE_SIMILARITY_THRESHOLD",
            retrieval.get("similarity_threshold"),
            normalizer=_to_float,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_max_chunk_chars",
            "KNOWLEDGE_MAX_CHUNK_CHARS",
            retrieval.get("max_chunk_chars"),
            normalizer=_to_int,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_timeout_seconds",
            "KNOWLEDGE_TIMEOUT_SECONDS",
            retrieval.get("timeout_seconds"),
            normalizer=_to_int,
        )
    summarizer = data.get("summarizer")
    if isinstance(summarizer, dict):
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_summarizer_provider",
            "KNOWLEDGE_SUMMARIZER_PROVIDER",
            summarizer.get("provider"),
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_summarizer_profile",
            "KNOWLEDGE_SUMMARIZER_PROFILE",
            summarizer.get("prompt_profile") or summarizer.get("profile"),
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_require_sources",
            "KNOWLEDGE_REQUIRE_SOURCES",
            summarizer.get("require_sources"),
            normalizer=_to_bool,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_no_evidence_policy",
            "KNOWLEDGE_NO_EVIDENCE_POLICY",
            summarizer.get("no_evidence_policy"),
            normalizer=_normalize_no_evidence_policy,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_max_answer_chars",
            "KNOWLEDGE_MAX_ANSWER_CHARS",
            summarizer.get("max_answer_chars"),
            normalizer=_to_int,
        )
        _overlay_value(
            overrides,
            env_vars,
            "knowledge_fallback_text",
            "KNOWLEDGE_FALLBACK_TEXT",
            summarizer.get("fallback_text"),
        )


def _overlay_fvs_config(overrides: dict[str, Any], env_vars: dict[str, str], path: Path) -> None:
    data = _load_optional_yaml(path)
    if not data:
        return
    _overlay_value(
        overrides,
        env_vars,
        "fvs_integration_mode",
        "FVS_INTEGRATION_MODE",
        data.get("integration_mode"),
        normalizer=_normalize_fvs_mode,
    )
    _overlay_value(overrides, env_vars, "fvs_url", "FVS_URL", data.get("url"))
    _overlay_value(overrides, env_vars, "fvs_target_origin", "FVS_TARGET_ORIGIN", data.get("target_origin"))


def _overlay_voice_config(overrides: dict[str, Any], env_vars: dict[str, str], path: Path) -> None:
    data = _load_optional_yaml(path)
    if not data:
        return
    asr = data.get("asr")
    if isinstance(asr, dict):
        _overlay_value(overrides, env_vars, "asr_provider", "ASR_PROVIDER", asr.get("provider"))
        _overlay_value(overrides, env_vars, "asr_model", "ASR_MODEL", asr.get("model"))
        _overlay_value(overrides, env_vars, "asr_region", "ASR_REGION", asr.get("region"))
        _overlay_value(overrides, env_vars, "asr_ws_url", "ASR_WS_URL", asr.get("ws_url"))
        _overlay_value(overrides, env_vars, "asr_audio_format", "ASR_AUDIO_FORMAT", asr.get("audio_format"))
        _overlay_value(
            overrides,
            env_vars,
            "asr_sample_rate",
            "ASR_SAMPLE_RATE",
            asr.get("sample_rate"),
            normalizer=_to_int,
        )
        _overlay_value(
            overrides,
            env_vars,
            "asr_timeout_seconds",
            "ASR_TIMEOUT_SECONDS",
            asr.get("timeout_seconds"),
            normalizer=_to_int,
        )
    tts = data.get("tts")
    if isinstance(tts, dict):
        _overlay_value(overrides, env_vars, "tts_provider", "TTS_PROVIDER", tts.get("provider"))
        _overlay_value(overrides, env_vars, "tts_model", "TTS_MODEL", tts.get("model"))
        _overlay_value(overrides, env_vars, "tts_voice", "TTS_VOICE", tts.get("voice"))
        _overlay_value(overrides, env_vars, "tts_ws_url", "TTS_WS_URL", tts.get("ws_url"))
        _overlay_value(overrides, env_vars, "tts_audio_format", "TTS_AUDIO_FORMAT", tts.get("audio_format"))
        _overlay_value(
            overrides,
            env_vars,
            "tts_streaming_enabled",
            "TTS_STREAMING_ENABLED",
            tts.get("streaming_enabled"),
            normalizer=_to_bool,
        )
        _overlay_value(
            overrides,
            env_vars,
            "tts_streaming_fallback",
            "TTS_STREAMING_FALLBACK",
            tts.get("streaming_fallback"),
            normalizer=_normalize_tts_streaming_fallback,
        )
        _overlay_value(
            overrides,
            env_vars,
            "tts_streaming_audio_format",
            "TTS_STREAMING_AUDIO_FORMAT",
            tts.get("streaming_audio_format"),
        )
        streaming = tts.get("streaming")
        if isinstance(streaming, dict):
            _overlay_value(
                overrides,
                env_vars,
                "tts_streaming_enabled",
                "TTS_STREAMING_ENABLED",
                streaming.get("enabled"),
                normalizer=_to_bool,
            )
            _overlay_value(
                overrides,
                env_vars,
                "tts_streaming_fallback",
                "TTS_STREAMING_FALLBACK",
                streaming.get("fallback"),
                normalizer=_normalize_tts_streaming_fallback,
            )
            _overlay_value(
                overrides,
                env_vars,
                "tts_streaming_audio_format",
                "TTS_STREAMING_AUDIO_FORMAT",
                streaming.get("audio_format"),
            )
        _overlay_value(
            overrides,
            env_vars,
            "tts_sample_rate",
            "TTS_SAMPLE_RATE",
            tts.get("sample_rate"),
            normalizer=_to_int,
        )
        _overlay_value(
            overrides,
            env_vars,
            "tts_timeout_seconds",
            "TTS_TIMEOUT_SECONDS",
            tts.get("timeout_seconds"),
            normalizer=_to_int,
        )


def _overlay_value(
    overrides: dict[str, Any],
    env_vars: dict[str, str],
    setting_name: str,
    env_key: str,
    value: Any,
    *,
    normalizer=None,
) -> None:
    if _has_env_override(env_vars, env_key) or value is None:
        return
    if normalizer is not None:
        value = normalizer(value)
    if value is None:
        return
    overrides[setting_name] = value


def _overlay_env_alias(
    overrides: dict[str, Any],
    env_vars: dict[str, str],
    setting_name: str,
    env_key: str,
    *,
    normalizer=None,
) -> None:
    value = env_vars.get(env_key.upper())
    if value is None or not value.strip():
        return
    if normalizer is not None:
        value = normalizer(value)
    if value is None:
        return
    overrides[setting_name] = value


def _overlay_path(
    overrides: dict[str, Any],
    env_vars: dict[str, str],
    setting_name: str,
    env_key: str,
    value: Any,
    base_dir: Path,
) -> None:
    if _has_env_override(env_vars, env_key, legacy_data_dir=setting_name == "ask_metrics_data_dir"):
        return
    if value in (None, ""):
        return
    overrides[setting_name] = str(_resolve_config_path(str(value), base_dir))


def _has_env_override(
    env_vars: dict[str, str],
    env_key: str,
    *,
    legacy_config_file: str | None = None,
    legacy_data_dir: bool = False,
) -> bool:
    value = env_vars.get(env_key.upper())
    if value is None or not value.strip():
        return False
    normalized = value.replace("\\", "/").rstrip("/")
    if legacy_config_file and normalized.endswith(f"/config/{legacy_config_file}"):
        return False
    return not (legacy_data_dir and normalized.endswith("/docs/demo_data/ask_metrics"))


def _resolve_config_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] in {"apps", "config", "data", "docs", "logs"}:
        return PROJECT_ROOT / path
    return base_dir / path


def _normalize_ask_metrics_mode(value: Any) -> str | None:
    mode = str(value or "").strip().lower()
    if mode not in {"excel", "dora", "auto"}:
        return None
    return mode


def _normalize_tts_streaming_fallback(value: Any) -> str | None:
    fallback = str(value or "").strip().lower()
    if fallback not in {"segment", "none"}:
        return None
    return fallback


def _normalize_fvs_mode(value: Any) -> str | None:
    mode = str(value or "").strip().lower()
    if mode not in {"mock", "iframe", "parent", "web-frame", "fvs-web-frame"}:
        return None
    if mode in {"web-frame", "fvs-web-frame"}:
        return "parent"
    return mode


def _normalize_knowledge_mode(value: Any) -> str | None:
    mode = str(value or "").strip().lower()
    if mode in {"dora", "auto"}:
        return mode
    if mode in {"local", "local_ragflow", "local_ragflow_llm", "knowledge_direct"}:
        return "local_ragflow_llm"
    return None


def _normalize_knowledge_transport(value: Any) -> str | None:
    transport = str(value or "").strip().lower()
    if transport in {"api", "ragflow_api", "retrieval_api"}:
        return "api"
    if transport in {"mcp", "streamable_http"}:
        return "mcp"
    return None


def _normalize_no_evidence_policy(value: Any) -> str | None:
    policy = str(value or "").strip().lower()
    if policy == "fallback":
        return policy
    return None


def _normalize_csv(value: Any) -> str | None:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    text = str(value or "").strip()
    return text or None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None
