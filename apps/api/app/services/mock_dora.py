from pathlib import Path
from uuid import uuid4

from app.models import ChatRequest, ChatResponse, ErrorDetail, ScreenControlAction
from app.services.screen_actions import ScreenActionService
from app.services.yaml_loader import load_yaml_file


class MockDoraService:
    def __init__(self, config_path: str | Path, action_service: ScreenActionService) -> None:
        self.config_path = Path(config_path)
        self.action_service = action_service
        self.config = load_yaml_file(self.config_path)

    def respond(self, request: ChatRequest) -> ChatResponse:
        rule = self._match_rule(request.text)
        if rule is None:
            return self._fallback(request)

        response_type = rule.get("response_type")
        if response_type == "screen_control":
            return self._screen_control(request, rule)
        if response_type == "answer":
            return self._answer(request, rule)

        return self._fallback(request, reason=f"Unsupported mock response type: {response_type}")

    def list_demo_questions(self) -> list[dict]:
        questions = self.config.get("demo_questions", [])
        if not isinstance(questions, list):
            return []
        return [question for question in questions if isinstance(question, dict)]

    def _match_rule(self, text: str) -> dict | None:
        for rule in self.config.get("mock_rules", []):
            keywords = rule.get("match_keywords", [])
            if any(str(keyword) in text for keyword in keywords):
                return rule
        return None

    def _answer(self, request: ChatRequest, rule: dict) -> ChatResponse:
        return ChatResponse(
            session_id=request.session_id,
            message_id=self._message_id(),
            type="answer",
            title=rule.get("title"),
            speak_text=rule.get("speak_text") or "我已收到您的问题。",
            display=rule.get("display"),
        )

    def _screen_control(self, request: ChatRequest, rule: dict) -> ChatResponse:
        action_id = str(rule.get("action_id") or "")
        action = self.action_service.get_action(action_id)
        if action is None:
            return self._fallback(
                request,
                reason="Mock Dora returned an action_id outside the whitelist",
                error=ErrorDetail(
                    code="ACTION_NOT_ALLOWED",
                    message=f"Action is not in whitelist: {action_id}",
                ),
            )

        return ChatResponse(
            session_id=request.session_id,
            message_id=self._message_id(),
            type="screen_control",
            speak_text=action.speak_text,
            action=ScreenControlAction(
                id=action.id,
                target=ScreenActionService.infer_target(action),
            ),
        )

    def _fallback(
        self,
        request: ChatRequest,
        reason: str | None = None,
        error: ErrorDetail | None = None,
    ) -> ChatResponse:
        fallback = self.config.get("fallback", {})
        return ChatResponse(
            session_id=request.session_id,
            message_id=self._message_id(),
            type="fallback",
            speak_text=fallback.get("speak_text") or "这个问题我还需要更多信息，请您换一种方式描述。",
            reason=reason or fallback.get("reason") or "无法判断用户意图",
            error=error,
        )

    @staticmethod
    def _message_id() -> str:
        return f"msg-{uuid4().hex[:12]}"
