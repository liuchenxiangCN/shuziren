import json
import logging
from dataclasses import dataclass
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import httpx

from app.models import ChatRequest


logger = logging.getLogger(__name__)


class DoraClientError(Exception):
    code = "DORA_ERROR"
    user_message = "Dora 服务暂时不可用，请稍后再试。"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.user_message)


class DoraConfigError(DoraClientError):
    code = "DORA_CONFIG_ERROR"
    user_message = "Dora 配置不完整，请检查后端环境变量。"


class DoraAgentResolveError(DoraClientError):
    code = "DORA_AGENT_RESOLVE_ERROR"
    user_message = "未能定位可用的 Dora Agent，请检查 Agent 配置。"


class DoraRequestError(DoraClientError):
    code = "DORA_REQUEST_ERROR"
    user_message = "Dora 服务暂时不可用，请稍后再试。"


@dataclass(frozen=True)
class DoraChatResult:
    raw_output: str
    agent_id: str
    message_id: str
    trace_id: str


@dataclass(frozen=True)
class SseEvent:
    event: str | None
    data: str


class DoraClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        agent_id: str,
        agent_name: str,
        channel_type: str,
        timeout_seconds: int,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.configured_agent_id = agent_id.strip()
        self.agent_name = agent_name.strip()
        self.channel_type = channel_type.strip() or "feishu"
        self.timeout_seconds = timeout_seconds
        self._resolved_agent_id: str | None = None

    def list_agents(self) -> list[dict[str, Any]]:
        self._validate_config(require_agent=False)
        payload = self._request_json("GET", "/external/api/openclaw/agents")
        return self._extract_agents(payload)

    def resolve_agent_id(self) -> str:
        if self.configured_agent_id:
            return self.configured_agent_id
        if self._resolved_agent_id:
            return self._resolved_agent_id

        if not self.agent_name:
            raise DoraAgentResolveError("DORA_AGENT_NAME is required when DORA_AGENT_ID is empty")

        matches = [
            agent
            for agent in self.list_agents()
            if self._agent_name(agent) == self.agent_name and self._is_published(agent)
        ]
        if not matches:
            raise DoraAgentResolveError(f"No published Dora agent matched name: {self.agent_name}")
        if len(matches) > 1:
            raise DoraAgentResolveError(
                f"Multiple published Dora agents matched name: {self.agent_name}"
            )

        agent_id = self._agent_id(matches[0])
        if not agent_id:
            raise DoraAgentResolveError("Matched Dora agent did not include an id")

        self._resolved_agent_id = agent_id
        return agent_id

    def sse_chat(self, request: ChatRequest, message_id: str | None = None) -> DoraChatResult:
        self._validate_config(require_agent=True)
        agent_id = self.resolve_agent_id()
        query_id = message_id or f"msg-{uuid4().hex[:12]}"
        trace_id = uuid4().hex
        payload = {
            "publishedAgentId": agent_id,
            "externalSessionKey": request.session_id,
            "queryId": query_id,
            "userMessage": request.text,
            "channelType": self.channel_type,
            "traceId": trace_id,
        }
        raw_output = self._post_sse("/external/api/openclaw/sse/chat", payload)
        return DoraChatResult(
            raw_output=raw_output,
            agent_id=agent_id,
            message_id=query_id,
            trace_id=trace_id,
        )

    def stream_sse_chat(self, request: ChatRequest, message_id: str | None = None) -> Iterator[SseEvent]:
        self._validate_config(require_agent=True)
        agent_id = self.resolve_agent_id()
        query_id = message_id or f"msg-{uuid4().hex[:12]}"
        trace_id = uuid4().hex
        payload = {
            "publishedAgentId": agent_id,
            "externalSessionKey": request.session_id,
            "queryId": query_id,
            "userMessage": request.text,
            "channelType": self.channel_type,
            "traceId": trace_id,
        }
        yield from self._stream_sse("/external/api/openclaw/sse/chat", payload)

    def _validate_config(self, *, require_agent: bool) -> None:
        if not self.base_url:
            raise DoraConfigError("DORA_BASE_URL is required")
        if not self.api_key:
            raise DoraConfigError("DORA_API_KEY is required")
        if require_agent and not self.configured_agent_id and not self.agent_name:
            raise DoraConfigError("DORA_AGENT_ID or DORA_AGENT_NAME is required")

    def _request_json(self, method: str, path: str) -> Any:
        try:
            with httpx.Client(timeout=self._timeout()) as client:
                response = client.request(
                    method,
                    self._url(path),
                    headers=self._headers(accept="application/json"),
                )
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as exc:
            raise DoraRequestError("Dora request timed out") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise DoraRequestError("Dora request failed") from exc

    def _post_sse(self, path: str, payload: dict[str, Any]) -> str:
        try:
            with httpx.Client(timeout=self._timeout()) as client:
                with client.stream(
                    "POST",
                    self._url(path),
                    headers=self._headers(accept="text/event-stream"),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type.lower():
                        return response.read().decode("utf-8", errors="replace").strip()
                    return self._collect_sse_output(self._iter_sse_events(response))
        except httpx.TimeoutException as exc:
            raise DoraRequestError("Dora SSE request timed out") from exc
        except httpx.HTTPError as exc:
            raise DoraRequestError("Dora SSE request failed") from exc

    def _stream_sse(self, path: str, payload: dict[str, Any]) -> Iterator[SseEvent]:
        try:
            with httpx.Client(timeout=self._timeout()) as client:
                with client.stream(
                    "POST",
                    self._url(path),
                    headers=self._headers(accept="text/event-stream"),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type.lower():
                        text = response.read().decode("utf-8", errors="replace").strip()
                        if text:
                            yield SseEvent(event="messages", data=text)
                        return
                    yield from self._iter_sse_event_stream(response)
        except httpx.TimeoutException as exc:
            raise DoraRequestError("Dora SSE request timed out") from exc
        except httpx.HTTPError as exc:
            raise DoraRequestError("Dora SSE request failed") from exc

    def _iter_sse_events(self, response: httpx.Response) -> list[SseEvent]:
        events: list[SseEvent] = []
        event_name: str | None = None
        data_lines: list[str] = []

        def flush() -> None:
            nonlocal event_name, data_lines
            if data_lines:
                events.append(SseEvent(event=event_name, data="\n".join(data_lines)))
            event_name = None
            data_lines = []

        for line in response.iter_lines():
            if line == "":
                flush()
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
                continue
            if line.startswith(("id:", "retry:")):
                continue
            if ":" in line:
                continue
            data_lines.append(line.strip())

        flush()
        return events

    def _iter_sse_event_stream(self, response: httpx.Response) -> Iterator[SseEvent]:
        event_name: str | None = None
        data_lines: list[str] = []

        def flush() -> SseEvent | None:
            nonlocal event_name, data_lines
            event = None
            if data_lines:
                event = SseEvent(event=event_name, data="\n".join(data_lines))
            event_name = None
            data_lines = []
            return event

        for line in response.iter_lines():
            if line == "":
                event = flush()
                if event is not None:
                    yield event
                continue
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line.removeprefix("event:").strip()
                continue
            if line.startswith("data:"):
                data_lines.append(line.removeprefix("data:").strip())
                continue
            if line.startswith(("id:", "retry:")):
                continue
            if ":" in line:
                continue
            data_lines.append(line.strip())

        event = flush()
        if event is not None:
            yield event

    def _collect_sse_output(self, events: list[SseEvent]) -> str:
        final_text: str | None = None
        chunks: list[str] = []

        for event in events:
            if event.event and event.event.lower() in {"metadata", "values"}:
                continue

            data = event.data.strip()
            if not data or data == "[DONE]":
                continue

            decoded = self._decode_json(data)
            if isinstance(decoded, dict) and decoded.get("type") in {
                "answer",
                "screen_control",
                "clarify",
                "fallback",
            }:
                final_text = json.dumps(decoded, ensure_ascii=False)
                continue

            extracted = self._extract_text(decoded, event.event)
            if extracted is None:
                continue

            text, is_final = extracted
            if is_final:
                final_text = text
            else:
                chunks.append(text)

        return (final_text or "".join(chunks)).strip()

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self, *, accept: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": accept,
            "Content-Type": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(float(self.timeout_seconds), read=float(self.timeout_seconds))

    @staticmethod
    def _decode_json(value: str) -> Any:
        try:
            return json.loads(value)
        except ValueError:
            return value

    @classmethod
    def _extract_text(cls, value: Any, event_name: str | None) -> tuple[str, bool] | None:
        final_event_names = {"answer", "final", "finished", "done", "end", "result"}
        is_final_event = (event_name or "").lower() in final_event_names

        if isinstance(value, str):
            return value, is_final_event

        if isinstance(value, list):
            parts: list[str] = []
            final = is_final_event
            for item in value:
                extracted = cls._extract_text(item, event_name)
                if extracted is None:
                    continue
                text, item_final = extracted
                parts.append(text)
                final = final or item_final
            if parts:
                return "".join(parts), final
            return None

        if not isinstance(value, dict):
            return None

        message_type = str(value.get("type") or "").lower()
        if message_type in {"tool", "toolmessage", "toolmessagechunk"}:
            return None

        if value.get("type") in {"answer", "screen_control", "clarify", "fallback"}:
            return json.dumps(value, ensure_ascii=False), True

        final_keys = (
            "answer",
            "finalAnswer",
            "final_answer",
            "output",
            "response",
            "result",
        )
        for key in final_keys:
            if key in value:
                extracted = cls._value_to_text(value[key], event_name)
                if extracted:
                    return extracted, True

        delta_keys = ("content", "text", "message", "delta")
        for key in delta_keys:
            if key in value:
                extracted = cls._value_to_text(value[key], event_name)
                if extracted:
                    return extracted, is_final_event

        if "data" in value:
            return cls._extract_text(value["data"], event_name)

        return None

    @classmethod
    def _value_to_text(cls, value: Any, event_name: str | None) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and "content" in value:
            return cls._value_to_text(value["content"], event_name)
        if isinstance(value, (dict, list)):
            extracted = cls._extract_text(value, event_name)
            if extracted:
                return extracted[0]
            return json.dumps(value, ensure_ascii=False)
        return None

    @classmethod
    def _extract_agents(cls, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]

        if isinstance(payload, dict):
            for key in ("data", "result", "records", "items", "list", "agents"):
                if key in payload:
                    agents = cls._extract_agents(payload[key])
                    if agents:
                        return agents

            for value in payload.values():
                agents = cls._extract_agents(value)
                if agents and any(cls._agent_name(agent) for agent in agents):
                    return agents

        return []

    @staticmethod
    def _agent_id(agent: dict[str, Any]) -> str:
        for key in ("publishedAgentId", "published_agent_id", "agentId", "agent_id", "id"):
            value = agent.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, int):
                return str(value)
        return ""

    @staticmethod
    def _agent_name(agent: dict[str, Any]) -> str:
        for key in ("name", "agentName", "agent_name", "publishedAgentName"):
            value = agent.get(key)
            if isinstance(value, str):
                return value.strip()
        return ""

    @staticmethod
    def _is_published(agent: dict[str, Any]) -> bool:
        has_signal = False

        if "published" in agent:
            has_signal = True
            if agent.get("published") is not True:
                return False

        for key in ("agentStatus", "status", "publishStatus", "publishedStatus"):
            if key not in agent:
                continue
            has_signal = True
            value = str(agent.get(key) or "").upper()
            if value != "PUBLISHED":
                return False

        return has_signal
