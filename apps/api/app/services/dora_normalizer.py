import json
import re
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from app.models import ChatRequest, ChatResponse, ErrorDetail, ScreenControlAction
from app.services.screen_actions import ScreenActionService


FALLBACK_SPEAK_TEXT = "这个问题我还需要更多信息，请您换一种方式描述。"
DORA_UNAVAILABLE_TEXT = "Dora 服务暂时不可用，请稍后再试。"


def normalize_dora_output(
    *,
    raw_output: Any,
    request: ChatRequest,
    action_service: ScreenActionService,
    message_id: str | None = None,
) -> ChatResponse:
    payload = _extract_payload(raw_output)
    response_message_id = message_id or _message_id()

    if isinstance(payload, dict):
        response_type = str(payload.get("type") or "").strip()
        if response_type == "screen_control":
            return _screen_control_response(
                request=request,
                payload=payload,
                action_service=action_service,
                message_id=response_message_id,
            )
        if response_type == "fallback":
            return _fallback_response(
                request=request,
                message_id=response_message_id,
                speak_text=_clean_text(payload.get("speak_text")) or FALLBACK_SPEAK_TEXT,
                reason=_clean_text(payload.get("reason")) or "Dora 返回兜底",
            )
        if response_type == "answer":
            return _answer_from_payload(request, payload, response_message_id)
        if response_type == "clarify":
            return _answer_from_clarify(request, payload, response_message_id)

        inferred_text = _find_text(payload)
        if inferred_text:
            return _answer_from_text(request, inferred_text, response_message_id)

        return _fallback_response(
            request=request,
            message_id=response_message_id,
            reason="Dora output type is unsupported",
            error=ErrorDetail(
                code="DORA_OUTPUT_INVALID",
                message="Dora output type is unsupported",
            ),
        )

    if isinstance(payload, str) and payload.strip():
        return _answer_from_text(request, payload.strip(), response_message_id)

    return _fallback_response(
        request=request,
        message_id=response_message_id,
        reason="Dora returned empty output",
        error=ErrorDetail(
            code="DORA_EMPTY_OUTPUT",
            message="Dora returned empty output",
        ),
    )


def dora_error_response(
    *,
    request: ChatRequest,
    message_id: str | None = None,
    code: str = "DORA_REQUEST_ERROR",
    speak_text: str = DORA_UNAVAILABLE_TEXT,
    reason: str = "Dora request failed",
) -> ChatResponse:
    return _fallback_response(
        request=request,
        message_id=message_id or _message_id(),
        speak_text=speak_text,
        reason=reason,
        error=ErrorDetail(code=code, message=speak_text),
    )


def _answer_from_payload(
    request: ChatRequest,
    payload: dict[str, Any],
    message_id: str,
) -> ChatResponse:
    speak_text = (
        _clean_text(payload.get("speak_text"))
        or _clean_text(payload.get("answer"))
        or _clean_text(payload.get("content"))
        or _clean_text(payload.get("text"))
        or _summary_from_display(payload.get("display"))
    )
    if not speak_text:
        return _fallback_response(
            request=request,
            message_id=message_id,
            reason="Dora answer is missing speak_text",
            error=ErrorDetail(
                code="DORA_OUTPUT_INVALID",
                message="Dora answer is missing speak_text",
            ),
        )

    display = payload.get("display")
    if not isinstance(display, dict):
        display = {"mode": "text", "summary": speak_text}

    return _safe_chat_response(
        ChatResponse(
            session_id=request.session_id,
            message_id=message_id,
            type="answer",
            title=_clean_text(payload.get("title")),
            speak_text=speak_text,
            display=display,
        )
    )


def _answer_from_clarify(
    request: ChatRequest,
    payload: dict[str, Any],
    message_id: str,
) -> ChatResponse:
    speak_text = _clean_text(payload.get("speak_text")) or FALLBACK_SPEAK_TEXT
    options = payload.get("options")
    bullets = [str(option) for option in options if option] if isinstance(options, list) else []
    return _safe_chat_response(
        ChatResponse(
            session_id=request.session_id,
            message_id=message_id,
            type="answer",
            title="请补充信息",
            speak_text=speak_text,
            display={
                "mode": "text",
                "summary": speak_text,
                "bullets": bullets,
            },
        )
    )


def _answer_from_text(request: ChatRequest, text: str, message_id: str) -> ChatResponse:
    speak_text = _clean_text(text) or FALLBACK_SPEAK_TEXT
    return _safe_chat_response(
        ChatResponse(
            session_id=request.session_id,
            message_id=message_id,
            type="answer",
            title="Dora 回答",
            speak_text=speak_text,
            display={
                "mode": "text",
                "summary": speak_text,
            },
        )
    )


def _screen_control_response(
    *,
    request: ChatRequest,
    payload: dict[str, Any],
    action_service: ScreenActionService,
    message_id: str,
) -> ChatResponse:
    action_payload = payload.get("action")
    if not isinstance(action_payload, dict):
        return _action_fallback(
            request=request,
            message_id=message_id,
            reason="Dora screen_control is missing action",
        )

    action_id = _clean_text(action_payload.get("id") or action_payload.get("action_id"))
    if not action_id:
        return _action_fallback(
            request=request,
            message_id=message_id,
            reason="Dora screen_control is missing action id",
        )

    action = action_service.get_action(action_id)
    if action is None:
        return _action_fallback(
            request=request,
            message_id=message_id,
            reason=f"Dora returned an action_id outside the whitelist: {action_id}",
        )

    return _safe_chat_response(
        ChatResponse(
            session_id=request.session_id,
            message_id=message_id,
            type="screen_control",
            speak_text=_clean_text(payload.get("speak_text")) or action.speak_text,
            action=ScreenControlAction(
                id=action.id,
                target=ScreenActionService.infer_target(action),
            ),
        )
    )


def _action_fallback(
    *,
    request: ChatRequest,
    message_id: str,
    reason: str,
) -> ChatResponse:
    return _fallback_response(
        request=request,
        message_id=message_id,
        speak_text="当前大屏暂不支持这个切换动作。",
        reason=reason,
        error=ErrorDetail(
            code="ACTION_NOT_ALLOWED",
            message="Action is not in whitelist",
        ),
    )


def _fallback_response(
    *,
    request: ChatRequest,
    message_id: str,
    speak_text: str = FALLBACK_SPEAK_TEXT,
    reason: str = "无法判断用户意图",
    error: ErrorDetail | None = None,
) -> ChatResponse:
    return _safe_chat_response(
        ChatResponse(
            session_id=request.session_id,
            message_id=message_id,
            type="fallback",
            speak_text=speak_text,
            reason=reason,
            error=error,
        )
    )


def _extract_payload(raw_output: Any) -> Any:
    if isinstance(raw_output, (dict, list)):
        return raw_output
    if not isinstance(raw_output, str):
        return raw_output

    text = raw_output.strip()
    if not text:
        return ""

    for block in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL):
        parsed = _try_json(block.strip())
        if parsed is not None:
            return parsed

    parsed = _try_json(text)
    if parsed is not None:
        return parsed

    parsed = _find_first_json_object(text)
    if parsed is not None:
        return parsed

    return text


def _find_first_json_object(text: str) -> Any | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except ValueError:
            continue
    return None


def _try_json(value: str) -> Any | None:
    try:
        return json.loads(value)
    except ValueError:
        return None


def _find_text(payload: dict[str, Any]) -> str | None:
    for key in (
        "speak_text",
        "answer",
        "content",
        "text",
        "message",
        "output",
        "response",
        "result",
    ):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = _find_text(value)
            if nested:
                return nested
    return None


def _summary_from_display(display: Any) -> str | None:
    if not isinstance(display, dict):
        return None
    summary = display.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return None


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _safe_chat_response(response: ChatResponse) -> ChatResponse:
    try:
        return ChatResponse.model_validate(response.model_dump())
    except ValidationError:
        return ChatResponse(
            session_id=response.session_id,
            message_id=response.message_id,
            type="fallback",
            speak_text=FALLBACK_SPEAK_TEXT,
            reason="Normalized Dora output failed validation",
            error=ErrorDetail(
                code="DORA_OUTPUT_INVALID",
                message="Normalized Dora output failed validation",
            ),
        )


def _message_id() -> str:
    return f"msg-{uuid4().hex[:12]}"
