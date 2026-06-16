from pathlib import Path
from typing import Any

from app.models import AuthorizedScreenAction, ErrorDetail, ScreenAction, ScreenExecuteResponse
from app.services.yaml_loader import load_yaml_file


_EXECUTOR_PROVIDER = "screen_action_whitelist"
_FVS_PROVIDER = "fvs"
_DANGEROUS_PARAM_KEY_PARTS = (
    "url",
    "uri",
    "href",
    "script",
    "javascript",
    "sh" "ell",
    "cmd",
    "command",
    "code",
    "html",
    "function",
)
_DANGEROUS_TEXT_PARTS = (
    "javascript:",
    "data:text/html",
    "<script",
    "</script",
    "e" "val(",
    "new " "function",
    "im" "port(",
    "sub" "process",
)


class ScreenActionService:
    def __init__(self, config_path: str | Path) -> None:
        self.config_path = Path(config_path)
        self._actions = self._load_actions()

    def _load_actions(self) -> dict[str, ScreenAction]:
        raw = load_yaml_file(self.config_path)
        raw_actions = raw.get("actions", {})
        if not isinstance(raw_actions, dict):
            raise ValueError("screen-actions.yaml actions must be an object")

        actions: dict[str, ScreenAction] = {}
        for action_id, action_config in raw_actions.items():
            if not isinstance(action_config, dict):
                continue
            actions[action_id] = ScreenAction(id=action_id, **action_config)
        return actions

    def list_actions(self) -> list[ScreenAction]:
        return list(self._actions.values())

    def get_action(self, action_id: str) -> ScreenAction | None:
        return self._actions.get(action_id)

    def execute(
        self,
        action_id: str,
        request_id: str | None = None,
        params: dict[str, Any] | None = None,
        target: str | None = None,
    ) -> ScreenExecuteResponse:
        action = self.get_action(action_id)
        if action is None:
            validation = self._rejected_validation(
                code="ACTION_NOT_ALLOWED",
                reason="Action is not in whitelist",
                request_params=params or {},
            )
            return ScreenExecuteResponse(
                success=False,
                action_id=action_id,
                speak_text="当前大屏暂不支持这个切换动作。",
                provider=_EXECUTOR_PROVIDER,
                validation=validation,
                rejection_reason=validation["reason"],
                request_id=request_id,
                error=ErrorDetail(
                    code="ACTION_NOT_ALLOWED",
                    message="Action is not in whitelist",
                ),
            )

        validation = self._validate_execution_request(action, params or {}, target=target)
        if validation["status"] != "authorized":
            return ScreenExecuteResponse(
                success=False,
                action_id=action.id,
                speak_text="当前大屏暂不支持这个切换动作。",
                target=self.infer_target(action),
                provider=_EXECUTOR_PROVIDER,
                validation=validation,
                rejection_reason=validation["reason"],
                request_id=request_id,
                error=ErrorDetail(
                    code=validation["code"],
                    message=validation["reason"],
                ),
            )

        authorized_action = self._authorized_action(action, validation=validation)
        return ScreenExecuteResponse(
            success=True,
            action_id=action.id,
            speak_text=action.speak_text,
            target=authorized_action.target,
            provider=authorized_action.provider,
            authorized_action=authorized_action,
            resolved_action=authorized_action,
            validation=validation,
            request_id=request_id,
        )

    @staticmethod
    def infer_target(action: ScreenAction) -> str | None:
        for key in ("tabId", "pageId"):
            value = action.params.get(key)
            if isinstance(value, str):
                return value
        page_number = action.params.get("pageNumber") or action.params.get("page_number")
        if isinstance(page_number, int) and page_number > 0:
            return f"page_number_{page_number}"
        return None

    def _authorized_action(self, action: ScreenAction, *, validation: dict[str, Any]) -> AuthorizedScreenAction:
        params = dict(validation.get("sanitized_params") or action.params)
        return AuthorizedScreenAction(
            id=action.id,
            action_id=action.id,
            label=action.label,
            type=action.type,
            description=action.description,
            target=self.infer_target(action),
            provider=_EXECUTOR_PROVIDER,
            fvs_function=action.fvs_function,
            fvs_routing=self._fvs_routing(action, params),
            params=params,
            speak_text=action.speak_text,
            validation=validation,
        )

    def _validate_execution_request(
        self,
        action: ScreenAction,
        request_params: dict[str, Any],
        *,
        target: str | None,
    ) -> dict[str, Any]:
        schema = self._params_schema(action)
        configured_params = self._sanitize_config_params(action.params)
        if configured_params["status"] != "authorized":
            return configured_params | {"params_schema": schema}

        target_status = self._validate_target(action, target)
        if target_status is not None:
            return self._rejected_validation(
                code="TARGET_NOT_ALLOWED",
                reason=target_status,
                request_params=request_params,
                params_schema=schema,
            )

        unknown_keys = [key for key in request_params if key not in action.params]
        if unknown_keys:
            return self._rejected_validation(
                code="PARAM_NOT_ALLOWED",
                reason=f"Params are not allowed for this action: {', '.join(sorted(unknown_keys))}",
                request_params=request_params,
                rejected_params=unknown_keys,
                params_schema=schema,
            )

        for key, raw_value in request_params.items():
            if not self._safe_param_key(key):
                return self._rejected_validation(
                    code="PARAM_NOT_ALLOWED",
                    reason=f"Param is not allowed for this action: {key}",
                    request_params=request_params,
                    rejected_params=[key],
                    params_schema=schema,
                )
            expected_value = configured_params["sanitized_params"][key]
            sanitized = self._sanitize_value(raw_value)
            if sanitized["status"] != "ok":
                return self._rejected_validation(
                    code="PARAM_INVALID",
                    reason=f"Param {key} is invalid: {sanitized['reason']}",
                    request_params=request_params,
                    rejected_params=[key],
                    params_schema=schema,
                )
            if sanitized["value"] != expected_value:
                return self._rejected_validation(
                    code="PARAM_VALUE_NOT_ALLOWED",
                    reason=f"Param {key} does not match the backend whitelist value",
                    request_params=request_params,
                    rejected_params=[key],
                    params_schema=schema,
                )

        return {
            "status": "authorized",
            "code": "AUTHORIZED",
            "reason": None,
            "provider": _EXECUTOR_PROVIDER,
            "params_schema": schema,
            "request_params": request_params,
            "sanitized_params": configured_params["sanitized_params"],
            "rejected_params": [],
        }

    def _validate_target(self, action: ScreenAction, target: str | None) -> str | None:
        if target is None or target == "":
            return None
        candidate = str(target).strip()
        allowed = {action.id, action.label}
        inferred = self.infer_target(action)
        if inferred:
            allowed.add(inferred)
        page_number = action.params.get("pageNumber") or action.params.get("page_number")
        if isinstance(page_number, int) and page_number > 0:
            allowed.add(str(page_number))
        if candidate in allowed:
            return None
        return "Target is not authorized for this action"

    def _sanitize_config_params(self, params: dict[str, Any]) -> dict[str, Any]:
        sanitized_params: dict[str, Any] = {}
        for key, raw_value in params.items():
            if not self._safe_param_key(key):
                return self._rejected_validation(
                    code="ACTION_CONFIG_INVALID",
                    reason=f"Configured param key is not allowed: {key}",
                    request_params={},
                    rejected_params=[key],
                )
            sanitized = self._sanitize_value(raw_value)
            if sanitized["status"] != "ok":
                return self._rejected_validation(
                    code="ACTION_CONFIG_INVALID",
                    reason=f"Configured param {key} is invalid: {sanitized['reason']}",
                    request_params={},
                    rejected_params=[key],
                )
            sanitized_params[key] = sanitized["value"]
        return {
            "status": "authorized",
            "code": "AUTHORIZED",
            "reason": None,
            "provider": _EXECUTOR_PROVIDER,
            "sanitized_params": sanitized_params,
            "rejected_params": [],
        }

    def _params_schema(self, action: ScreenAction) -> dict[str, Any]:
        properties = {}
        for key, value in action.params.items():
            properties[key] = {
                "type": self._schema_type(value),
                "required_value": value,
                "client_override": "must_match_backend_value",
            }
            if key in {"pageNumber", "page_number"}:
                properties[key]["minimum"] = 1
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        }

    def _fvs_routing(self, action: ScreenAction, params: dict[str, Any]) -> dict[str, Any]:
        page_number = params.get("pageNumber") or params.get("page_number")
        if isinstance(page_number, int) and page_number > 0:
            return {
                "provider": _FVS_PROVIDER,
                "mode": "iframe_page_number",
                "function": action.fvs_function,
                "page_param": "page_number",
                "page_number": page_number,
            }
        return {
            "provider": _FVS_PROVIDER,
            "mode": "post_message",
            "message_type": "FVS_ACTION",
            "function": action.fvs_function,
        }

    def _rejected_validation(
        self,
        *,
        code: str,
        reason: str,
        request_params: dict[str, Any],
        rejected_params: list[str] | None = None,
        params_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "rejected",
            "code": code,
            "reason": reason,
            "provider": _EXECUTOR_PROVIDER,
            "params_schema": params_schema or {"type": "object", "additionalProperties": False, "properties": {}},
            "request_params": self._request_param_summary(request_params),
            "sanitized_params": {},
            "rejected_params": sorted(rejected_params or []),
        }

    @staticmethod
    def _safe_param_key(key: str) -> bool:
        if not key or len(key) > 64:
            return False
        if not key[0].isalpha():
            return False
        if not all(char.isalnum() or char == "_" for char in key):
            return False
        normalized = key.lower()
        return not any(part in normalized for part in _DANGEROUS_PARAM_KEY_PARTS)

    @staticmethod
    def _sanitize_value(value: Any) -> dict[str, Any]:
        if isinstance(value, bool):
            return {"status": "ok", "value": value}
        if isinstance(value, int) and not isinstance(value, bool):
            if value < 0 or value > 10_000:
                return {"status": "error", "reason": "integer out of allowed range"}
            return {"status": "ok", "value": value}
        if isinstance(value, float):
            if value < 0 or value > 10_000:
                return {"status": "error", "reason": "number out of allowed range"}
            return {"status": "ok", "value": value}
        if isinstance(value, str):
            text = value.strip()
            if len(text) > 120:
                return {"status": "error", "reason": "string is too long"}
            lowered = text.lower()
            if any(part.lower() in lowered for part in _DANGEROUS_TEXT_PARTS):
                return {"status": "error", "reason": "string contains executable content"}
            if "://" in lowered:
                return {"status": "error", "reason": "URL values are not allowed in action params"}
            if any(char in text for char in "<>`\r\n"):
                return {"status": "error", "reason": "string contains unsafe characters"}
            return {"status": "ok", "value": text}
        return {"status": "error", "reason": "nested or unsupported values are not allowed"}

    @staticmethod
    def _request_param_summary(params: dict[str, Any]) -> dict[str, Any]:
        return {
            str(key): {
                "provided": True,
                "type": type(value).__name__,
            }
            for key, value in params.items()
        }

    @staticmethod
    def _schema_type(value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int) and not isinstance(value, bool):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        return "unsupported"
