import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

from app.services.screen_actions import ScreenActionService
from app.services.yaml_loader import load_yaml_file


def _resolve_project_root() -> Path:
    current = Path(__file__).resolve()
    candidates = [Path.cwd(), *current.parents]
    for candidate in candidates:
        if (candidate / "config").exists():
            return candidate
    return Path.cwd()


PROJECT_ROOT = _resolve_project_root()
CONFIG_OVERRIDE_VERSION = 1
RUNTIME_OVERRIDE_SOURCE = "runtime_override"
DEFAULT_OVERRIDE_DIR = PROJECT_ROOT / "data" / "config-overrides"

_SAFE_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")
_SAFE_ACTION_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SQL_RE = re.compile(r"\b(select|insert|update|delete|drop|alter|create|truncate|grant|revoke|merge)\b", re.IGNORECASE)
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "access_key",
    "secret",
    "token",
    "password",
    "passwd",
    "dsn",
    "bearer",
    "credential",
    "private_key",
)
_BLOCKED_KEY_PARTS = ("sql", "query", "statement", "script", "command", "shell", "python", "javascript")
_EXECUTABLE_TEXT_PARTS = (
    "javascript:",
    "data:text/html",
    "<script",
    "</script",
    "eval(",
    "new function",
    "import(",
    "subprocess",
    "os.system",
    "python -c",
    "python3 -c",
    "python.exe",
    "powershell",
    "cmd.exe",
    "#!/bin",
)
_SECRET_QUERY_KEYS = {"token", "access_token", "api_key", "apikey", "key", "secret", "password", "auth", "authorization"}


class ConfigOverrideService:
    def __init__(self, override_dir: str | Path | None = None) -> None:
        self.override_dir = _safe_override_dir(override_dir)
        self.active_path = self.override_dir / "active.yaml"
        self.history_dir = self.override_dir / "history"
        self.audit_path = self.override_dir / "audit.jsonl"

    def read_active_document(self) -> dict[str, Any]:
        if not self.active_path.exists():
            return {"version": CONFIG_OVERRIDE_VERSION, "overrides": {}}
        try:
            data = load_yaml_file(self.active_path)
        except Exception:
            return {"version": CONFIG_OVERRIDE_VERSION, "overrides": {}}
        if not isinstance(data.get("overrides"), dict):
            data["overrides"] = {}
        return data

    def read_active_overrides(self) -> dict[str, Any]:
        document = self.read_active_document()
        overrides = document.get("overrides")
        return overrides if isinstance(overrides, dict) else {}

    def screen_action_overrides(self) -> dict[str, Any]:
        return screen_action_overrides_from_active(self.read_active_overrides())

    def metadata(self) -> dict[str, Any]:
        document = self.read_active_document()
        return {
            "version": document.get("version", CONFIG_OVERRIDE_VERSION),
            "path": _display_path(self.active_path),
            "exists": self.active_path.exists(),
            "updated_at": document.get("updated_at"),
            "updated_by": document.get("updated_by"),
            "reason": document.get("reason"),
            "sha256": _sha256_yaml(document.get("overrides", {})),
        }

    def active_response(self, *, access: dict[str, Any]) -> dict[str, Any]:
        return {
            **self.metadata(),
            "access": access,
            "overrides": self.read_active_overrides(),
        }

    def validate(
        self,
        overrides: dict[str, Any],
        *,
        base_action_path: str | Path,
        dry_run: bool,
    ) -> dict[str, Any]:
        normalized, errors, warnings = normalize_overrides(overrides)
        action_preview: list[dict[str, Any]] = []
        if not errors:
            action_overrides = screen_action_overrides_from_active(normalized)
            try:
                preview_service = ScreenActionService(base_action_path, overrides=action_overrides)
                for action_id in sorted(action_overrides):
                    response = preview_service.execute(action_id)
                    if not response.success:
                        errors.append(
                            {
                                "path": f"capabilities.screen_control.actions.{action_id}",
                                "code": response.error.code if response.error else "ACTION_CONFIG_INVALID",
                                "message": response.rejection_reason or "Action override failed dry-run validation",
                            }
                        )
                action_preview = [
                    action.model_dump(mode="json")
                    for action in preview_service.list_actions()
                    if action.id in action_overrides
                ]
            except Exception as exc:
                errors.append(
                    {
                        "path": "capabilities.screen_control.actions",
                        "code": "ACTION_CONFIG_INVALID",
                        "message": f"Action overrides failed validation: {exc}",
                    }
                )
        summary = _validation_summary(normalized, action_preview)
        return {
            "ok": not errors,
            "dry_run": dry_run,
            "summary": summary,
            "errors": errors,
            "warnings": warnings,
            "normalized_overrides": normalized if not errors else {},
            "effective_preview": _effective_preview(normalized),
            "action_preview": action_preview,
        }

    def save(
        self,
        overrides: dict[str, Any],
        *,
        operator: str,
        reason: str,
        base_action_path: str | Path,
    ) -> dict[str, Any]:
        validation = self.validate(overrides, base_action_path=base_action_path, dry_run=False)
        if not validation["ok"]:
            self.append_audit(
                action="save_rejected",
                operator=operator,
                reason=reason,
                ok=False,
                summary=validation["summary"],
                errors=validation["errors"],
            )
            return validation

        normalized = validation["normalized_overrides"]
        document = {
            "version": CONFIG_OVERRIDE_VERSION,
            "updated_at": _now_iso(),
            "updated_by": operator,
            "reason": reason,
            "overrides": normalized,
        }
        self.override_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        rendered = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
        temp_path = self.active_path.with_suffix(".tmp")
        temp_path.write_text(rendered, encoding="utf-8")
        temp_path.replace(self.active_path)

        history_path = self.history_dir / f"{_file_timestamp()}-{_safe_slug(operator)}.yaml"
        history_path.write_text(rendered, encoding="utf-8")

        self.append_audit(
            action="save",
            operator=operator,
            reason=reason,
            ok=True,
            summary=validation["summary"],
            errors=[],
            active_sha256=_sha256_text(rendered),
        )
        return validation

    def append_audit(
        self,
        *,
        action: str,
        operator: str,
        reason: str,
        ok: bool,
        summary: dict[str, Any],
        errors: list[dict[str, Any]],
        active_sha256: str | None = None,
    ) -> None:
        self.override_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event_id": hashlib.sha256(f"{_now_iso()}:{operator}:{action}".encode("utf-8")).hexdigest()[:16],
            "created_at": _now_iso(),
            "operator": operator,
            "action": action,
            "reason": reason,
            "ok": ok,
            "summary": summary,
            "errors": errors,
            "active_sha256": active_sha256 or self.metadata().get("sha256"),
        }
        with self.audit_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def audit_events(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.audit_path.exists():
            return []
        lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        events: list[dict[str, Any]] = []
        for line in reversed(lines[-limit:]):
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                events.append(item)
        return events


def apply_settings_overrides(settings: Any) -> Any:
    service = ConfigOverrideService(getattr(settings, "config_overrides_dir", None))
    active = service.read_active_overrides()
    normalized, errors, _warnings = normalize_overrides(active)
    if errors:
        return settings

    env = _configured_env_vars()
    updates: dict[str, Any] = {}

    def apply(path: tuple[str, ...], setting_name: str, *env_keys: str) -> None:
        if any(_has_env_value(env, key) for key in env_keys):
            return
        found, value = _get_path(normalized, path)
        if found:
            updates[setting_name] = value

    apply(("project", "project_name"), "project_name", "PROJECT_NAME")
    apply(("project", "product_name"), "product_name", "PRODUCT_NAME")
    apply(("customer", "customer_name"), "customer_name", "CUSTOMER_NAME")
    apply(("customer", "scenario_name"), "scenario_name", "SCENARIO_NAME")
    apply(("customer", "assistant_name"), "assistant_name", "ASSISTANT_NAME")
    apply(("dashboard", "fvs_integration_mode"), "fvs_integration_mode", "FVS_INTEGRATION_MODE", "VITE_FVS_INTEGRATION_MODE")
    apply(("dashboard", "fvs_url"), "fvs_url", "FVS_URL", "VITE_FVS_URL")
    apply(("dashboard", "fvs_target_origin"), "fvs_target_origin", "FVS_TARGET_ORIGIN", "VITE_FVS_TARGET_ORIGIN")
    apply(("capabilities", "ask_metrics", "mode"), "ask_metrics_mode", "ASK_METRICS_MODE")
    apply(("capabilities", "knowledge", "mode"), "knowledge_mode", "KNOWLEDGE_MODE")
    apply(("capabilities", "knowledge", "retrieval", "page_size"), "knowledge_page_size", "KNOWLEDGE_PAGE_SIZE")
    apply(("capabilities", "knowledge", "retrieval", "top_k"), "knowledge_top_k", "KNOWLEDGE_TOP_K")
    apply(
        ("capabilities", "knowledge", "retrieval", "similarity_threshold"),
        "knowledge_similarity_threshold",
        "KNOWLEDGE_SIMILARITY_THRESHOLD",
    )
    apply(("capabilities", "knowledge", "retrieval", "max_chunk_chars"), "knowledge_max_chunk_chars", "KNOWLEDGE_MAX_CHUNK_CHARS")
    apply(("capabilities", "knowledge", "summarizer", "profile"), "knowledge_summarizer_profile", "KNOWLEDGE_SUMMARIZER_PROFILE")
    apply(("capabilities", "knowledge", "summarizer", "require_sources"), "knowledge_require_sources", "KNOWLEDGE_REQUIRE_SOURCES")
    apply(
        ("capabilities", "knowledge", "summarizer", "no_evidence_policy"),
        "knowledge_no_evidence_policy",
        "KNOWLEDGE_NO_EVIDENCE_POLICY",
    )
    apply(("mock_switches", "demo_stable_mode"), "demo_stable_mode", "DEMO_STABLE_MODE")

    if not updates:
        return settings
    return settings.model_copy(update=updates)


def screen_action_overrides_from_active(overrides: dict[str, Any]) -> dict[str, Any]:
    actions = (
        overrides.get("capabilities", {})
        if isinstance(overrides.get("capabilities"), dict)
        else {}
    ).get("screen_control", {})
    if not isinstance(actions, dict):
        return {}
    raw_actions = actions.get("actions")
    return raw_actions if isinstance(raw_actions, dict) else {}


def normalize_overrides(raw: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not isinstance(raw, dict):
        return {}, [_error("$", "INVALID_TYPE", "Overrides must be an object")], warnings

    _scan_keys_and_values(raw, "$", errors)
    normalized: dict[str, Any] = {}
    allowed_top = {"project", "customer", "dashboard", "capabilities", "mock_switches"}
    for key in raw:
        if key not in allowed_top:
            errors.append(_error(key, "FIELD_NOT_ALLOWED", "This override section is not editable in stage 5"))

    _normalize_project(raw.get("project"), normalized, errors)
    _normalize_customer(raw.get("customer"), normalized, errors)
    _normalize_dashboard(raw.get("dashboard"), normalized, errors)
    _normalize_capabilities(raw.get("capabilities"), normalized, errors, warnings)
    _normalize_mock_switches(raw.get("mock_switches"), normalized, errors)
    return normalized, errors, warnings


def _normalize_project(raw: Any, normalized: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "project", errors)
    if data is None:
        return
    section: dict[str, Any] = {}
    for key in data:
        if key not in {"project_name", "product_name"}:
            errors.append(_error(f"project.{key}", "FIELD_NOT_ALLOWED", "Only project_name and product_name are editable"))
    for key in ("project_name", "product_name"):
        if key in data:
            value = _safe_text(data[key], f"project.{key}", errors, max_length=80)
            if value is not None:
                section[key] = value
    if section:
        normalized["project"] = section


def _normalize_customer(raw: Any, normalized: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "customer", errors)
    if data is None:
        return
    section: dict[str, Any] = {}
    allowed = {"customer_name", "scenario_name", "assistant_name"}
    for key in data:
        if key not in allowed:
            errors.append(_error(f"customer.{key}", "FIELD_NOT_ALLOWED", "Customer ID and paths are not editable here"))
    for key in allowed:
        if key in data:
            value = _safe_text(data[key], f"customer.{key}", errors, max_length=80)
            if value is not None:
                section[key] = value
    if section:
        normalized["customer"] = section


def _normalize_dashboard(raw: Any, normalized: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "dashboard", errors)
    if data is None:
        return
    section: dict[str, Any] = {}
    allowed = {"fvs_integration_mode", "fvs_url", "fvs_target_origin"}
    for key in data:
        if key not in allowed:
            errors.append(_error(f"dashboard.{key}", "FIELD_NOT_ALLOWED", "Only non-sensitive FVS runtime fields are editable"))
    if "fvs_integration_mode" in data:
        mode = str(data["fvs_integration_mode"] or "").strip().lower()
        if mode not in {"mock", "iframe", "parent"}:
            errors.append(_error("dashboard.fvs_integration_mode", "INVALID_VALUE", "Allowed values: mock, iframe, parent"))
        else:
            section["fvs_integration_mode"] = mode
    if "fvs_url" in data:
        value = _safe_url(data["fvs_url"], "dashboard.fvs_url", errors, allow_relative=True)
        if value is not None:
            section["fvs_url"] = value
    if "fvs_target_origin" in data:
        value = _safe_origin(data["fvs_target_origin"], "dashboard.fvs_target_origin", errors)
        if value is not None:
            section["fvs_target_origin"] = value
    if section:
        normalized["dashboard"] = section


def _normalize_capabilities(
    raw: Any,
    normalized: dict[str, Any],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "capabilities", errors)
    if data is None:
        return
    section: dict[str, Any] = {}
    for key in data:
        if key not in {"ask_metrics", "knowledge", "screen_control"}:
            errors.append(_error(f"capabilities.{key}", "FIELD_NOT_ALLOWED", "Capability section is not editable"))
    _normalize_ask_metrics(data.get("ask_metrics"), section, errors)
    _normalize_knowledge(data.get("knowledge"), section, errors, warnings)
    _normalize_screen_control(data.get("screen_control"), section, errors)
    if section:
        normalized["capabilities"] = section


def _normalize_ask_metrics(raw: Any, section: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "capabilities.ask_metrics", errors)
    if data is None:
        return
    for key in data:
        if key != "mode":
            errors.append(_error(f"capabilities.ask_metrics.{key}", "FIELD_NOT_ALLOWED", "Database Provider and SQL config are not editable in stage 5"))
    mode = str(data.get("mode") or "").strip().lower()
    if mode:
        if mode not in {"excel", "dora", "auto"}:
            errors.append(_error("capabilities.ask_metrics.mode", "INVALID_VALUE", "Allowed values: excel, dora, auto; database remains not_implemented"))
        else:
            section.setdefault("ask_metrics", {})["mode"] = mode


def _normalize_knowledge(
    raw: Any,
    section: dict[str, Any],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "capabilities.knowledge", errors)
    if data is None:
        return
    allowed = {"mode", "retrieval", "summarizer"}
    target: dict[str, Any] = {}
    for key in data:
        if key not in allowed:
            errors.append(_error(f"capabilities.knowledge.{key}", "FIELD_NOT_ALLOWED", "External LLM summarizer config is not editable in this stage"))
    if "mode" in data:
        mode = str(data["mode"] or "").strip().lower()
        if mode not in {"dora", "local_ragflow_llm", "auto"}:
            errors.append(_error("capabilities.knowledge.mode", "INVALID_VALUE", "Allowed values: dora, local_ragflow_llm, auto"))
        else:
            target["mode"] = mode
    retrieval = data.get("retrieval")
    if retrieval is not None:
        retrieval_data = _expect_object(retrieval, "capabilities.knowledge.retrieval", errors)
        if retrieval_data is not None:
            retrieval_section: dict[str, Any] = {}
            for key in retrieval_data:
                if key not in {"page_size", "top_k", "similarity_threshold", "max_chunk_chars"}:
                    errors.append(_error(f"capabilities.knowledge.retrieval.{key}", "FIELD_NOT_ALLOWED", "RAGFlow endpoints, keys and transports are not editable here"))
            _optional_int(retrieval_data, retrieval_section, "page_size", "capabilities.knowledge.retrieval.page_size", errors, min_value=1, max_value=10)
            _optional_int(retrieval_data, retrieval_section, "top_k", "capabilities.knowledge.retrieval.top_k", errors, min_value=1, max_value=64)
            _optional_float(
                retrieval_data,
                retrieval_section,
                "similarity_threshold",
                "capabilities.knowledge.retrieval.similarity_threshold",
                errors,
                min_value=0.0,
                max_value=1.0,
            )
            _optional_int(
                retrieval_data,
                retrieval_section,
                "max_chunk_chars",
                "capabilities.knowledge.retrieval.max_chunk_chars",
                errors,
                min_value=200,
                max_value=4000,
            )
            if retrieval_section:
                target["retrieval"] = retrieval_section
    summarizer = data.get("summarizer")
    if summarizer is not None:
        summarizer_data = _expect_object(summarizer, "capabilities.knowledge.summarizer", errors)
        if summarizer_data is not None:
            summarizer_section: dict[str, Any] = {}
            for key in summarizer_data:
                if key not in {"profile", "require_sources", "no_evidence_policy"}:
                    errors.append(_error(f"capabilities.knowledge.summarizer.{key}", "FIELD_NOT_ALLOWED", "External LLM provider, model and prompt text are not editable"))
            if "profile" in summarizer_data:
                profile = str(summarizer_data["profile"] or "").strip()
                if not _SAFE_PROFILE_RE.match(profile):
                    errors.append(_error("capabilities.knowledge.summarizer.profile", "INVALID_VALUE", "Profile must be an identifier, not prompt content"))
                else:
                    summarizer_section["profile"] = profile
                    if profile != "source_bound_extractive":
                        warnings.append(
                            _warning(
                                "capabilities.knowledge.summarizer.profile",
                                "PROFILE_LABEL_ONLY",
                                "Only source_bound_extractive is implemented; non-default profile is saved as a label and does not enable external LLM summarizer.",
                            )
                        )
            if "require_sources" in summarizer_data:
                summarizer_section["require_sources"] = bool(summarizer_data["require_sources"])
            if "no_evidence_policy" in summarizer_data:
                policy = str(summarizer_data["no_evidence_policy"] or "").strip().lower()
                if policy != "fallback":
                    errors.append(_error("capabilities.knowledge.summarizer.no_evidence_policy", "INVALID_VALUE", "Only fallback is allowed"))
                else:
                    summarizer_section["no_evidence_policy"] = policy
            if summarizer_section:
                target["summarizer"] = summarizer_section
    if target:
        section["knowledge"] = target


def _normalize_screen_control(raw: Any, section: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "capabilities.screen_control", errors)
    if data is None:
        return
    for key in data:
        if key != "actions":
            errors.append(_error(f"capabilities.screen_control.{key}", "FIELD_NOT_ALLOWED", "Only action mappings are editable"))
    actions_raw = data.get("actions")
    if actions_raw is None:
        return
    actions = _expect_object(actions_raw, "capabilities.screen_control.actions", errors)
    if actions is None:
        return
    normalized_actions: dict[str, Any] = {}
    for action_id, raw_action in actions.items():
        path = f"capabilities.screen_control.actions.{action_id}"
        if not _SAFE_ACTION_ID_RE.match(str(action_id)):
            errors.append(_error(path, "INVALID_ACTION_ID", "Action ID must use uppercase letters, numbers and underscore"))
            continue
        action_data = _expect_object(raw_action, path, errors)
        if action_data is None:
            continue
        allowed = {"label", "type", "description", "fvs_function", "params", "speak_text"}
        for key in action_data:
            if key not in allowed:
                errors.append(_error(f"{path}.{key}", "FIELD_NOT_ALLOWED", "Action override cannot contain executable routing fields"))
        action: dict[str, Any] = {}
        label = _safe_text(action_data.get("label"), f"{path}.label", errors, max_length=40, required=True)
        if label is not None:
            action["label"] = label
        action_type = str(action_data.get("type") or "page").strip().lower()
        if action_type != "page":
            errors.append(_error(f"{path}.type", "INVALID_VALUE", "Only page actions are editable in this stage"))
        action["type"] = "page"
        description = _safe_text(action_data.get("description", ""), f"{path}.description", errors, max_length=120)
        action["description"] = description or ""
        fvs_function = str(action_data.get("fvs_function") or "gotoPage").strip()
        if fvs_function != "gotoPage":
            errors.append(_error(f"{path}.fvs_function", "INVALID_VALUE", "Only gotoPage is allowed in writable action config"))
        action["fvs_function"] = "gotoPage"
        params = _expect_object(action_data.get("params"), f"{path}.params", errors)
        if params is None:
            continue
        for key in params:
            if key not in {"pageNumber", "page_number"}:
                errors.append(_error(f"{path}.params.{key}", "FIELD_NOT_ALLOWED", "Only pageNumber is allowed; URLs, scripts and arbitrary params are blocked"))
        page_number = params.get("pageNumber", params.get("page_number"))
        try:
            page_number_int = int(page_number)
        except (TypeError, ValueError):
            errors.append(_error(f"{path}.params.pageNumber", "INVALID_VALUE", "pageNumber must be an integer"))
            continue
        if page_number_int < 1 or page_number_int > 10_000:
            errors.append(_error(f"{path}.params.pageNumber", "INVALID_VALUE", "pageNumber is out of range"))
            continue
        action["params"] = {"pageNumber": page_number_int}
        speak_text = _safe_text(action_data.get("speak_text"), f"{path}.speak_text", errors, max_length=120, required=True)
        if speak_text is not None:
            action["speak_text"] = speak_text
        normalized_actions[str(action_id)] = action
    if normalized_actions:
        section.setdefault("screen_control", {})["actions"] = normalized_actions


def _normalize_mock_switches(raw: Any, normalized: dict[str, Any], errors: list[dict[str, Any]]) -> None:
    if raw is None:
        return
    data = _expect_object(raw, "mock_switches", errors)
    if data is None:
        return
    section: dict[str, Any] = {}
    for key in data:
        if key != "demo_stable_mode":
            errors.append(_error(f"mock_switches.{key}", "FIELD_NOT_ALLOWED", "Only demo_stable_mode is editable; provider credentials stay in env"))
    if "demo_stable_mode" in data:
        section["demo_stable_mode"] = bool(data["demo_stable_mode"])
    if section:
        normalized["mock_switches"] = section


def _expect_object(value: Any, path: str, errors: list[dict[str, Any]]) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    errors.append(_error(path, "INVALID_TYPE", "Expected an object"))
    return None


def _safe_text(
    value: Any,
    path: str,
    errors: list[dict[str, Any]],
    *,
    max_length: int,
    required: bool = False,
) -> str | None:
    if value in (None, ""):
        if required:
            errors.append(_error(path, "REQUIRED", "Value is required"))
        return None
    text = str(value).strip()
    if not text:
        if required:
            errors.append(_error(path, "REQUIRED", "Value is required"))
        return None
    if len(text) > max_length:
        errors.append(_error(path, "TOO_LONG", f"Value must be at most {max_length} characters"))
        return None
    if _has_blocked_text(text):
        errors.append(_error(path, "UNSAFE_TEXT", "Executable code, SQL or secret-looking content is not allowed"))
        return None
    return text


def _safe_url(value: Any, path: str, errors: list[dict[str, Any]], *, allow_relative: bool) -> str | None:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if len(text) > 500:
        errors.append(_error(path, "TOO_LONG", "URL is too long"))
        return None
    lowered = text.lower()
    if lowered.startswith(("javascript:", "data:", "file:", "ftp:")) or _has_blocked_text(text, allow_sql_words=True):
        errors.append(_error(path, "UNSAFE_URL", "URL scheme or content is not allowed"))
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        errors.append(_error(path, "INVALID_URL", "URL cannot be parsed"))
        return None
    if parts.username or parts.password:
        errors.append(_error(path, "UNSAFE_URL", "URL credentials are not allowed"))
        return None
    if parts.query:
        for key, _raw_value in parse_qsl(parts.query, keep_blank_values=True):
            lowered_key = key.lower()
            if lowered_key in _SECRET_QUERY_KEYS or any(part in lowered_key for part in ("token", "secret", "password")):
                errors.append(_error(path, "SECRET_QUERY_PARAM", "Secret-looking URL query parameters are not allowed"))
                return None
    if parts.scheme:
        if parts.scheme not in {"http", "https"}:
            errors.append(_error(path, "INVALID_URL", "Only http and https URLs are allowed"))
            return None
        return text
    if allow_relative and text.startswith("/") and not text.startswith("//") and ".." not in Path(text).parts:
        return text
    errors.append(_error(path, "INVALID_URL", "Use an http(s) URL or an absolute same-origin path"))
    return None


def _safe_origin(value: Any, path: str, errors: list[dict[str, Any]]) -> str | None:
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if text == "*":
        errors.append(_error(path, "INVALID_ORIGIN", "Wildcard target origin is not allowed in writable config"))
        return None
    url = _safe_url(text, path, errors, allow_relative=False)
    if url is None:
        return None
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def _optional_int(
    source: dict[str, Any],
    target: dict[str, Any],
    key: str,
    path: str,
    errors: list[dict[str, Any]],
    *,
    min_value: int,
    max_value: int,
) -> None:
    if key not in source:
        return
    try:
        value = int(source[key])
    except (TypeError, ValueError):
        errors.append(_error(path, "INVALID_VALUE", "Expected an integer"))
        return
    if value < min_value or value > max_value:
        errors.append(_error(path, "OUT_OF_RANGE", f"Expected {min_value}..{max_value}"))
        return
    target[key] = value


def _optional_float(
    source: dict[str, Any],
    target: dict[str, Any],
    key: str,
    path: str,
    errors: list[dict[str, Any]],
    *,
    min_value: float,
    max_value: float,
) -> None:
    if key not in source:
        return
    try:
        value = float(source[key])
    except (TypeError, ValueError):
        errors.append(_error(path, "INVALID_VALUE", "Expected a number"))
        return
    if value < min_value or value > max_value:
        errors.append(_error(path, "OUT_OF_RANGE", f"Expected {min_value}..{max_value}"))
        return
    target[key] = value


def _scan_keys_and_values(value: Any, path: str, errors: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                errors.append(_error(f"{path}.{key_text}", "SENSITIVE_FIELD_BLOCKED", "Sensitive fields must stay in environment variables"))
            if lowered != "description" and any(part in lowered for part in _BLOCKED_KEY_PARTS):
                errors.append(_error(f"{path}.{key_text}", "EXECUTABLE_FIELD_BLOCKED", "Executable code, SQL and arbitrary commands are not configurable"))
            _scan_keys_and_values(item, f"{path}.{key_text}", errors)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_keys_and_values(item, f"{path}[{index}]", errors)
    elif isinstance(value, str) and _has_blocked_text(value):
        errors.append(_error(path, "UNSAFE_TEXT", "Executable code, SQL or secret-looking content is not allowed"))


def _has_blocked_text(text: str, *, allow_sql_words: bool = False) -> bool:
    lowered = text.lower()
    if any(part in lowered for part in _EXECUTABLE_TEXT_PARTS):
        return True
    if re.search(r"\b(sk|ak)-[A-Za-z0-9_\-]{6,}\b", text):
        return True
    if "bearer " in lowered:
        return True
    if not allow_sql_words and _SQL_RE.search(text):
        return True
    return False


def _validation_summary(normalized: dict[str, Any], action_preview: list[dict[str, Any]]) -> dict[str, Any]:
    changed = _flatten_paths(normalized)
    return {
        "changed_paths": changed,
        "changed_count": len(changed),
        "action_override_count": len(action_preview),
        "database_provider": "not_implemented",
        "llm_summarizer": "not_implemented",
        "secrets_allowed": False,
    }


def _effective_preview(normalized: dict[str, Any]) -> dict[str, Any]:
    return {
        "project": normalized.get("project", {}),
        "customer": normalized.get("customer", {}),
        "dashboard": normalized.get("dashboard", {}),
        "ask_metrics": _get_path(normalized, ("capabilities", "ask_metrics"))[1] if _get_path(normalized, ("capabilities", "ask_metrics"))[0] else {},
        "knowledge": _get_path(normalized, ("capabilities", "knowledge"))[1] if _get_path(normalized, ("capabilities", "knowledge"))[0] else {},
        "mock_switches": normalized.get("mock_switches", {}),
    }


def _flatten_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(item, dict):
                result.extend(_flatten_paths(item, path))
            else:
                result.append(path)
        return result
    return [prefix] if prefix else []


def _get_path(value: dict[str, Any], path: tuple[str, ...]) -> tuple[bool, Any]:
    current: Any = value
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


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


def _safe_override_dir(value: str | Path | None) -> Path:
    if value:
        path = Path(value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        try:
            resolved = path.resolve()
        except OSError:
            return DEFAULT_OVERRIDE_DIR
        try:
            resolved.relative_to(PROJECT_ROOT / "data")
            return resolved
        except ValueError:
            return DEFAULT_OVERRIDE_DIR
    return DEFAULT_OVERRIDE_DIR


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _error(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def _warning(path: str, code: str, message: str) -> dict[str, str]:
    return {"path": path, "code": code, "message": message}


def _sha256_yaml(value: Any) -> str:
    return _sha256_text(yaml.safe_dump(value or {}, allow_unicode=True, sort_keys=True))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())[:40].strip("-")
    return slug or "operator"


def _file_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    try:
        tz = ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        tz = timezone(timedelta(hours=8), name="Asia/Shanghai")
    return datetime.now(tz).isoformat(timespec="seconds")
