from pathlib import Path
from typing import Any

from app.models import ErrorDetail, ScreenAction, ScreenExecuteResponse
from app.services.yaml_loader import load_yaml_file


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
        self, action_id: str, request_id: str | None = None, params: dict[str, Any] | None = None
    ) -> ScreenExecuteResponse:
        action = self.get_action(action_id)
        if action is None:
            return ScreenExecuteResponse(
                success=False,
                action_id=action_id,
                speak_text="当前大屏暂不支持这个切换动作。",
                request_id=request_id,
                error=ErrorDetail(
                    code="ACTION_NOT_ALLOWED",
                    message="Action is not in whitelist",
                ),
            )

        return ScreenExecuteResponse(
            success=True,
            action_id=action.id,
            speak_text=action.speak_text,
            request_id=request_id,
        )

    @staticmethod
    def infer_target(action: ScreenAction) -> str | None:
        for key in ("tabId", "pageId"):
            value = action.params.get(key)
            if isinstance(value, str):
                return value
        return None

