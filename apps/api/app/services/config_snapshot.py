import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import PROJECT_ROOT, Settings
from app.services.screen_actions import ScreenActionService
from app.services.yaml_loader import load_yaml_file


CONFIG_SNAPSHOT_VERSION = "1.0"
SOURCES = [
    "code_default",
    "root_config",
    "customer_config",
    "env",
    "frontend_build",
    "frontend_runtime",
    "derived",
    "unknown",
]

SENSITIVE_ENV_KEYS = {
    "DORA_API_KEY": "Dora API Key",
    "RAGFLOW_API_KEY": "RAGFlow API Key",
    "ASR_API_KEY": "ASR API Key",
    "TTS_API_KEY": "TTS API Key",
    "METRICS_DB_DSN": "Metrics database DSN",
}

SECRET_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "bearer",
    "code",
    "dsn",
    "key",
    "password",
    "secret",
    "token",
}


class ConfigSourceTracker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.env = _configured_env_vars()
        self.customer_id = settings.customer_id.strip() or "default"
        self.customer_dir = _safe_path(settings.customer_config_dir) or (
            PROJECT_ROOT / "config" / "customers" / self.customer_id
        )
        self.runtime = _load_optional_yaml(self.customer_dir / "runtime.yaml")
        self.dora = _load_optional_yaml(self.customer_dir / "dora.yaml")
        self.ragflow = _load_optional_yaml(self.customer_dir / "ragflow.yaml")
        self.fvs = _load_optional_yaml(self.customer_dir / "fvs.yaml")
        self.voice = _load_optional_yaml(self.customer_dir / "voice.yaml")
        self.ask_metrics = _load_optional_yaml(self.customer_dir / "ask-metrics.yaml")

    def env_source(self, *keys: str) -> str | None:
        for key in keys:
            if _has_env_value(self.env, key):
                return "env"
        return None

    def project_source(self, setting_name: str, env_key: str) -> str:
        if self.env_source(env_key):
            return "env"
        project = self.runtime.get("project")
        if isinstance(project, dict) and project.get(setting_name) is not None:
            return "customer_config"
        if self.runtime.get(setting_name) is not None:
            return "customer_config"
        return "code_default"

    def customer_id_source(self) -> str:
        return self.env_source("CUSTOMER_ID") or "code_default"

    def customer_dir_source(self) -> str:
        if self.env_source("CUSTOMER_CONFIG_DIR"):
            return "env"
        if self.customer_dir.exists():
            return "derived"
        return "derived"

    def demo_stable_source(self) -> str:
        if self.env_source("DEMO_STABLE_MODE"):
            return "env"
        demo = self.runtime.get("demo")
        if self.runtime.get("demo_stable_mode") is not None:
            return "customer_config"
        if isinstance(demo, dict) and demo.get("stable_mode") is not None:
            return "customer_config"
        return "code_default"

    def ask_metrics_mode_source(self) -> str:
        if self.env_source("ASK_METRICS_MODE"):
            return "env"
        runtime_ask = self.runtime.get("ask_metrics")
        if isinstance(runtime_ask, dict) and runtime_ask.get("mode") is not None:
            return "customer_config"
        if self.runtime.get("ask_metrics_mode") is not None:
            return "customer_config"
        if self.ask_metrics.get("mode") is not None:
            return "customer_config"
        root_config = _load_optional_yaml(PROJECT_ROOT / "config" / "ask-metrics.yaml")
        if root_config.get("mode") is not None:
            return "root_config"
        return "code_default"

    def config_file_source(self, value: str, env_key: str, legacy_name: str) -> str:
        if _has_env_value(self.env, env_key) and not _is_legacy_config_path(self.env[env_key.upper()], legacy_name):
            return "env"
        path = _safe_path(value)
        if path is None:
            return "unknown"
        try:
            path.relative_to(self.customer_dir)
            return "customer_config"
        except ValueError:
            pass
        try:
            path.relative_to(PROJECT_ROOT / "config")
            return "root_config"
        except ValueError:
            return "derived"

    def ask_metrics_data_dir_source(self) -> str:
        if _has_env_value(self.env, "ASK_METRICS_DATA_DIR") and not _is_legacy_data_dir(
            self.env["ASK_METRICS_DATA_DIR"]
        ):
            return "env"
        runtime_ask = self.runtime.get("ask_metrics")
        if isinstance(runtime_ask, dict) and runtime_ask.get("data_dir") is not None:
            return "customer_config"
        if self.ask_metrics.get("data_dir") is not None:
            return "customer_config"
        return "code_default"

    def dora_source(self, env_key: str, yaml_key: str) -> str:
        if self.env_source(env_key):
            return "env"
        if self.dora.get(yaml_key) is not None:
            return "customer_config"
        return "code_default"

    def ragflow_source(self, env_key: str, yaml_key: str) -> str:
        if self.env_source(env_key):
            return "env"
        if self.ragflow.get(yaml_key) is not None:
            return "customer_config"
        return "code_default"

    def fvs_source(self, env_key: str, yaml_key: str, *aliases: str) -> str:
        if self.env_source(env_key, *aliases):
            return "env"
        if self.fvs.get(yaml_key) is not None:
            return "customer_config"
        return "code_default"

    def voice_source(self, section: str, env_key: str, yaml_key: str) -> str:
        if self.env_source(env_key):
            return "env"
        data = self.voice.get(section)
        if isinstance(data, dict) and data.get(yaml_key) is not None:
            return "customer_config"
        return "code_default"

    def mock_source(self, env_key: str) -> str:
        return self.env_source(env_key) or "code_default"

    def secret_source(self, env_key: str) -> str:
        return self.env_source(env_key) or "code_default"


def build_config_effective(
    settings: Settings,
    action_service: ScreenActionService,
) -> dict[str, Any]:
    tracker = ConfigSourceTracker(settings)
    action_count = _action_count(action_service)
    generated_at = _now_iso()

    return {
        "version": CONFIG_SNAPSHOT_VERSION,
        "generated_at": generated_at,
        "read_only": True,
        "provenance": {
            "sources": SOURCES,
            "notes": [
                "本接口按白名单构造 ConfigSnapshot, 不返回 Settings 全量 dump。",
                "当前配置加载器仍以合并后 Settings 驱动运行; 阶段 1 对部分聚合字段只能标 derived 或 unknown。",
                "前端浏览器 URL 参数和 Vite 构建变量由前端页面单独展示, 后端只能描述其契约。",
            ],
        },
        "project": {
            "project_id": _field(settings.project_id, tracker.project_source("project_id", "PROJECT_ID")),
            "project_name": _field(settings.project_name, tracker.project_source("project_name", "PROJECT_NAME")),
            "product_name": _field(settings.product_name, tracker.project_source("product_name", "PRODUCT_NAME")),
        },
        "customer": {
            "customer_id": _field(settings.customer_id, tracker.customer_id_source()),
            "customer_name": _field(settings.customer_name, tracker.project_source("customer_name", "CUSTOMER_NAME")),
            "customer_config_dir": _field(
                _display_path(settings.customer_config_dir),
                tracker.customer_dir_source(),
                notes="默认路径由 customer_id 推导; 若目录不存在, 仍只作为候选客户配置目录。",
            ),
            "scenario_name": _field(settings.scenario_name, tracker.project_source("scenario_name", "SCENARIO_NAME")),
            "assistant_name": _field(
                settings.assistant_name,
                tracker.project_source("assistant_name", "ASSISTANT_NAME"),
            ),
        },
        "dashboard": {
            "backend_effective": {
                "provider": _field(
                    "mock_fvs" if settings.enable_mock_fvs else "fvs",
                    "derived",
                    notes="由 ENABLE_MOCK_FVS 与 FVS 配置组合推导。",
                ),
                "integration_mode": _field(
                    settings.fvs_integration_mode,
                    tracker.fvs_source("FVS_INTEGRATION_MODE", "integration_mode", "VITE_FVS_INTEGRATION_MODE"),
                ),
                "url": _field(
                    _redact_text(settings.fvs_url),
                    tracker.fvs_source("FVS_URL", "url", "VITE_FVS_URL"),
                    notes="URL 查询参数中的 token/key/password 等敏感参数会被脱敏。",
                ),
                "target_origin": _field(
                    _redact_text(settings.fvs_target_origin),
                    tracker.fvs_source("FVS_TARGET_ORIGIN", "target_origin", "VITE_FVS_TARGET_ORIGIN"),
                ),
                "action_whitelist_path": _field(
                    _display_path(settings.action_whitelist_path),
                    tracker.config_file_source(
                        settings.action_whitelist_path,
                        "ACTION_WHITELIST_PATH",
                        "screen-actions.yaml",
                    ),
                ),
                "action_count": _field(
                    action_count,
                    "derived",
                    notes="由当前 ScreenActionService 已加载白名单计算。",
                ),
            },
            "frontend_runtime_contract": {
                "integration_mode": _field(
                    "VITE_FVS_INTEGRATION_MODE 或 URL 参数 fvs_mode",
                    "frontend_build",
                    notes="浏览器实际值在前端页面内读取。",
                ),
                "url": _field(
                    "VITE_FVS_URL 或 URL 参数 fvs_url",
                    "frontend_runtime",
                    notes="后端无法读取用户当前浏览器 URL 参数; 页面会展示当前浏览器 runtime。",
                ),
                "target_origin": _field(
                    "VITE_FVS_TARGET_ORIGIN 或 URL 参数 fvs_origin",
                    "frontend_runtime",
                ),
            },
        },
        "capabilities": {
            "ask_metrics": {
                "mode": _field(settings.ask_metrics_mode, tracker.ask_metrics_mode_source()),
                "current_provider": _field(_ask_metrics_current_provider(settings.ask_metrics_mode), "derived"),
                "provider_interface": _status_field(
                    "implemented",
                    "阶段 2 已抽象 AskMetricsProvider; Excel 问数由配置驱动的 ExcelAskMetricsProvider 承接。",
                ),
                "implemented_providers": ["excel", "dora", "auto"],
                "planned_providers": ["database"],
                "excel_provider": _status_field(
                    "implemented",
                    "Excel Provider 只读读取配置声明的 workbook/sheet/metric 模板。",
                ),
                "database_provider": _status_field(
                    "not_implemented",
                    "阶段 2 仅预留 Database Provider 状态; 不连接数据库, 不执行 SQL, 不让模型生成 SQL。",
                ),
                "config_path": _field(
                    _display_path(settings.ask_metrics_config_path),
                    tracker.config_file_source(
                        settings.ask_metrics_config_path,
                        "ASK_METRICS_CONFIG_PATH",
                        "ask-metrics.yaml",
                    ),
                ),
                "data_dir": _field(
                    _display_path(settings.ask_metrics_data_dir),
                    tracker.ask_metrics_data_dir_source(),
                ),
            },
            "knowledge": {
                "current_provider": _field("dora_ragflow_mcp", "derived"),
                "implemented_providers": ["dora_ragflow_mcp"],
                "planned_providers": ["local_ragflow_llm"],
                "ragflow_base_url": _field(
                    _redact_text(settings.ragflow_base_url),
                    tracker.ragflow_source("RAGFLOW_BASE_URL", "base_url"),
                ),
                "ragflow_mcp_url": _field(
                    _redact_text(settings.ragflow_mcp_url),
                    tracker.ragflow_source("RAGFLOW_MCP_URL", "mcp_url"),
                ),
                "knowledge_direct_adapter": _status_field(
                    "not_implemented",
                    "阶段 3 前未实现 KnowledgeDirectAdapter 或 LLM summarizer。",
                ),
            },
            "screen_control": {
                "resolver": _field(
                    "dora_or_mock",
                    "derived",
                    notes="当前没有本地 ScreenControlResolver; Dora/Mock 仅产出 action_id。",
                ),
                "executor": _field("fvs_whitelist", "root_config" if action_count else "derived"),
                "execute_api": _field("/api/screen/execute", "code_default"),
                "execute_returns_authorized_action": _field(
                    False,
                    "code_default",
                    notes="阶段 4 前响应不包含完整 authorized_action。",
                ),
                "writable_action_config": _status_field(
                    "not_implemented",
                    "阶段 5 前不开放 action 写入、reload 或 dry-run。",
                ),
            },
            "dora": {
                "enabled": _field(not settings.enable_mock_dora, tracker.mock_source("ENABLE_MOCK_DORA")),
                "base_url": _field(
                    _redact_text(settings.dora_base_url),
                    tracker.dora_source("DORA_BASE_URL", "base_url"),
                ),
                "agent_id_configured": _field(bool(settings.dora_agent_id), tracker.dora_source("DORA_AGENT_ID", "agent_id")),
                "agent_name": _field(
                    settings.dora_agent_name,
                    tracker.dora_source("DORA_AGENT_NAME", "agent_name"),
                ),
                "channel_type": _field(
                    settings.dora_channel_type,
                    tracker.dora_source("DORA_CHANNEL_TYPE", "channel_type"),
                ),
                "chat_mode": _field(settings.dora_chat_mode, tracker.dora_source("DORA_CHAT_MODE", "chat_mode")),
            },
            "voice": {
                "asr_provider": _field(settings.asr_provider, tracker.voice_source("asr", "ASR_PROVIDER", "provider")),
                "asr_model": _field(settings.asr_model, tracker.voice_source("asr", "ASR_MODEL", "model")),
                "tts_provider": _field(settings.tts_provider, tracker.voice_source("tts", "TTS_PROVIDER", "provider")),
                "tts_model": _field(settings.tts_model, tracker.voice_source("tts", "TTS_MODEL", "model")),
                "tts_voice": _field(settings.tts_voice, tracker.voice_source("tts", "TTS_VOICE", "voice")),
                "tts_streaming_enabled": _field(
                    settings.tts_streaming_enabled,
                    tracker.voice_source("tts", "TTS_STREAMING_ENABLED", "streaming_enabled"),
                ),
                "tts_streaming_fallback": _field(
                    settings.tts_streaming_fallback,
                    tracker.voice_source("tts", "TTS_STREAMING_FALLBACK", "streaming_fallback"),
                ),
            },
        },
        "mock_switches": {
            "dora": _field(settings.enable_mock_dora, tracker.mock_source("ENABLE_MOCK_DORA")),
            "asr": _field(settings.enable_mock_asr, tracker.mock_source("ENABLE_MOCK_ASR")),
            "tts": _field(settings.enable_mock_tts, tracker.mock_source("ENABLE_MOCK_TTS")),
            "fvs": _field(settings.enable_mock_fvs, tracker.mock_source("ENABLE_MOCK_FVS")),
            "demo_stable_mode": _field(settings.demo_stable_mode, tracker.demo_stable_source()),
        },
        "prompt_profiles": {
            "dora_direct_mode": {
                "profile": _field(
                    settings.dora_agent_name or "mock_dora",
                    tracker.dora_source("DORA_AGENT_NAME", "agent_name")
                    if settings.dora_agent_name
                    else "derived",
                    notes="真实 Prompt 当前维护在 Dora Agent; 本项目不提供可写 Prompt。",
                ),
                "writable": False,
            },
            "knowledge_summarizer": {
                "profile": _field(
                    None,
                    "unknown",
                    notes="阶段 3 前未实现本地 knowledge summarizer prompt profile。",
                ),
                "writable": False,
            },
            "screen_resolver": {
                "profile": _field(
                    None,
                    "unknown",
                    notes="阶段 4 前未实现本地 screen resolver prompt profile。",
                ),
                "writable": False,
            },
        },
        "implementation_status": {
            "readonly_config_api": "implemented",
            "readonly_config_page": "implemented",
            "writable_config": "not_implemented",
            "config_validate_api": "not_implemented",
            "config_test_api": "not_implemented",
            "config_reload_api": "not_implemented",
            "config_audit_api": "not_implemented",
            "ask_metrics_provider_interface": "implemented",
            "excel_ask_metrics_provider": "implemented",
            "database_provider": "not_implemented",
            "knowledge_direct_adapter": "not_implemented",
            "llm_summarizer": "not_implemented",
            "writable_prompt": "not_implemented",
            "screen_execute_authorized_action_response": "not_implemented",
        },
        "sensitive": _sensitive_snapshot(settings, tracker),
    }


def build_config_schema() -> dict[str, Any]:
    return {
        "version": CONFIG_SNAPSHOT_VERSION,
        "generated_at": _now_iso(),
        "read_only": True,
        "sources": SOURCES,
        "sections": {
            "project": {
                "description": "项目、客户、场景和助手展示字段。",
                "editable_stage": 5,
                "sensitive": False,
            },
            "dashboard": {
                "description": "后端 FVS effective 配置和前端 runtime 配置契约。",
                "editable_stage": 5,
                "sensitive": False,
                "notes": "阶段 1 不允许保存或 reload; 浏览器 runtime 由前端展示。",
            },
            "ask_metrics": {
                "description": "当前 ASK_METRICS_MODE、AskMetricsProvider 抽象与 Excel/Dora/auto 实现状态。",
                "editable_stage": 2,
                "planned": ["database_provider"],
                "sensitive": False,
                "notes": "阶段 2 已实现配置驱动 Excel Provider; Database Provider 仍为 not_implemented。",
            },
            "knowledge": {
                "description": "当前 Dora -> RAGFlow MCP 知识库路径与后续本地直连状态。",
                "editable_stage": 3,
                "planned": ["KnowledgeDirectAdapter", "LLM summarizer"],
                "sensitive": False,
            },
            "screen_control": {
                "description": "action_id 白名单执行现状。",
                "editable_stage": 4,
                "planned": ["authorized_action response", "local resolver", "writable action config"],
                "sensitive": False,
            },
            "mock_switches": {
                "description": "Dora/ASR/TTS/FVS Mock 开关与演示稳态开关。",
                "editable_stage": 5,
                "sensitive": False,
            },
            "sensitive": {
                "description": "API Key、Token、密码、DSN 等敏感项只返回 configured/source/masked。",
                "editable_stage": None,
                "sensitive": True,
            },
        },
        "disabled_endpoints": [
            "PUT /api/config/overrides",
            "POST /api/config/validate",
            "POST /api/config/test",
            "POST /api/config/reload",
            "GET /api/config/audit",
        ],
    }


def _field(value: Any, source: str, *, sensitive: bool = False, notes: str | None = None) -> dict[str, Any]:
    result = {
        "value": value,
        "source": source,
        "sensitive": sensitive,
    }
    if notes:
        result["notes"] = notes
    return result


def _status_field(status: str, notes: str) -> dict[str, Any]:
    return {
        "status": status,
        "source": "code_default",
        "sensitive": False,
        "notes": notes,
    }


def _sensitive_snapshot(settings: Settings, tracker: ConfigSourceTracker) -> dict[str, Any]:
    env = tracker.env
    values = {
        "DORA_API_KEY": settings.dora_api_key,
        "RAGFLOW_API_KEY": settings.ragflow_api_key,
        "ASR_API_KEY": settings.asr_api_key,
        "TTS_API_KEY": settings.tts_api_key,
        "METRICS_DB_DSN": env.get("METRICS_DB_DSN", ""),
    }
    return {
        key.lower(): {
            "label": SENSITIVE_ENV_KEYS[key],
            "configured": bool(str(value or "").strip()),
            "source": tracker.secret_source(key),
            "sensitive": True,
            "masked": _masked_summary(value),
        }
        for key, value in values.items()
    }


def _masked_summary(value: Any) -> str:
    text = str(value or "")
    if not text.strip():
        return "not_configured"
    return f"configured:length={len(text)}"


def _ask_metrics_current_provider(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized == "excel":
        return "excel"
    if normalized == "dora":
        return "dora"
    if normalized == "auto":
        return "dora_then_excel_fallback"
    return "excel"


def _action_count(action_service: ScreenActionService) -> int:
    try:
        return len(action_service.list_actions())
    except Exception:
        return 0


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


def _has_env_value(env: dict[str, str], key: str) -> bool:
    value = env.get(key.upper())
    return value is not None and bool(value.strip())


def _load_optional_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = load_yaml_file(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_path(value: str | None) -> Path | None:
    if not value:
        return None
    try:
        return Path(value).resolve()
    except OSError:
        return None


def _display_path(value: str) -> str:
    path = _safe_path(value)
    if path is None:
        return ""
    try:
        return str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _is_legacy_config_path(value: str, file_name: str) -> bool:
    normalized = value.replace("\\", "/").rstrip("/")
    return normalized.endswith(f"/config/{file_name}")


def _is_legacy_data_dir(value: str) -> bool:
    normalized = value.replace("\\", "/").rstrip("/")
    return normalized.endswith("/docs/demo_data/ask_metrics")


def _redact_text(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    text = _redact_url_query(text)
    patterns = [
        (re.compile(r"Bearer\s+[A-Za-z0-9._~+\-/=]+", re.IGNORECASE), "Bearer ***"),
        (re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{6,}\b"), "sk-***"),
        (re.compile(r"\bak-[A-Za-z0-9][A-Za-z0-9_\-]{6,}\b", re.IGNORECASE), "ak-***"),
    ]
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    return text


def _redact_url_query(value: str) -> str:
    if "?" not in value:
        return value
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.query:
        return value
    query = []
    for key, raw_value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SECRET_QUERY_KEYS or any(token in key.lower() for token in ("token", "secret", "password")):
            query.append((key, "***"))
        else:
            query.append((key, raw_value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _now_iso() -> str:
    try:
        tz = ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
    return datetime.now(tz).isoformat(timespec="seconds")
