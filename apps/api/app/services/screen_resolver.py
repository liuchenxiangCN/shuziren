from dataclasses import dataclass

from app.models import ChatRequest, ChatResponse, ScreenControlAction
from app.services.screen_actions import ScreenActionService


_SCREEN_INTENT_TERMS = (
    "切换",
    "切到",
    "打开",
    "返回",
    "回到",
    "进入",
    "跳转",
    "查看",
    "显示",
    "看一下",
)

_HOME_ALIASES = ("首页", "主页", "主屏", "首屏")


@dataclass(frozen=True)
class ScreenResolveResult:
    action_id: str
    target: str | None
    provider: str
    reason: str


class ScreenControlResolver:
    """Local rule resolver that only emits candidate action_id values."""

    provider = "local_rules"

    def __init__(self, action_service: ScreenActionService) -> None:
        self.action_service = action_service

    def resolve(self, text: str) -> ScreenResolveResult | None:
        normalized = text.strip()
        if not normalized or not self._has_screen_intent(normalized):
            return None

        for action in self.action_service.list_actions():
            candidates = [action.label, action.description]
            if action.id == "SWITCH_HOME":
                candidates.extend(_HOME_ALIASES)
            for candidate in candidates:
                candidate_text = str(candidate or "").strip()
                if candidate_text and candidate_text in normalized:
                    return ScreenResolveResult(
                        action_id=action.id,
                        target=ScreenActionService.infer_target(action),
                        provider=self.provider,
                        reason=f"matched configured action label: {candidate_text}",
                    )
        return None

    def to_chat_response(
        self,
        request: ChatRequest,
        result: ScreenResolveResult,
        *,
        message_id: str,
    ) -> ChatResponse:
        action = self.action_service.get_action(result.action_id)
        if action is None:
            raise ValueError(f"Resolved action no longer exists in whitelist: {result.action_id}")
        return ChatResponse(
            session_id=request.session_id,
            message_id=message_id,
            type="screen_control",
            speak_text=action.speak_text,
            display={
                "mode": "screen_control",
                "summary": action.description or action.label,
                "audit": {
                    "capability": "screen_control",
                    "resolver": result.provider,
                    "candidate_action_id": result.action_id,
                    "reason": result.reason,
                    "executor": "fvs_whitelist",
                },
            },
            action=ScreenControlAction(
                id=action.id,
                target=ScreenActionService.infer_target(action),
            ),
        )

    @staticmethod
    def _has_screen_intent(text: str) -> bool:
        return any(term in text for term in _SCREEN_INTENT_TERMS)
