from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


ResponseType = Literal["answer", "screen_control", "clarify", "fallback"]


class ErrorDetail(BaseModel):
    code: str
    message: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    version: str


class ChatRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: f"demo-session-{uuid4().hex[:8]}")
    text: str = Field(min_length=1, max_length=1000)
    context: dict[str, Any] = Field(default_factory=dict)


class ScreenControlAction(BaseModel):
    id: str
    target: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    type: ResponseType
    speak_text: str
    title: str | None = None
    display: dict[str, Any] | None = None
    action: ScreenControlAction | None = None
    reason: str | None = None
    options: list[str] | None = None
    error: ErrorDetail | None = None


class AsrTranscribeRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: f"demo-session-{uuid4().hex[:8]}")
    mock_text: str | None = Field(default=None, max_length=1000)
    audio_base64: str | None = Field(default=None, max_length=8_000_000)
    audio_format: str | None = Field(default=None, max_length=80)


class AsrTranscribeResponse(BaseModel):
    success: bool
    session_id: str
    text: str
    provider: str
    mock: bool
    duration_ms: int | None = None
    error: ErrorDetail | None = None


class WakeSettings(BaseModel):
    min_audio_ms: int = Field(default=800, ge=200, le=10_000)
    max_audio_ms: int = Field(default=5_000, ge=500, le=30_000)
    cooldown_ms: int = Field(default=1_500, ge=0, le=30_000)
    require_exact_phrase: bool = False
    vad_threshold: float = Field(default=0.018, ge=0.001, le=0.5)
    silence_ms: int = Field(default=700, ge=100, le=5_000)
    command_timeout_ms: int = Field(default=8_000, ge=1_000, le=30_000)
    followup_enabled: bool = True
    followup_window_ms: int = Field(default=12_000, ge=1_000, le=60_000)
    max_followup_turns: int = Field(default=3, ge=0, le=20)
    barge_in_enabled: bool = False
    barge_in_wake_words: list[str] = Field(default_factory=list)
    barge_in_vad_threshold: float = Field(default=0.018, ge=0.001, le=0.5)
    barge_in_min_audio_ms: int = Field(default=900, ge=200, le=10_000)
    barge_in_silence_ms: int = Field(default=700, ge=100, le=5_000)
    barge_in_max_audio_ms: int = Field(default=3_500, ge=500, le=30_000)
    barge_in_ignore_after_tts_start_ms: int = Field(default=700, ge=0, le=5_000)


class WakeConfigResponse(BaseModel):
    version: str
    mode: str
    wake_words: list[str]
    settings: WakeSettings = Field(default_factory=WakeSettings)


class DemoConfigResponse(BaseModel):
    stable_mode: bool
    project_id: str
    project_name: str
    product_name: str
    customer_id: str
    customer_name: str
    scenario_name: str
    assistant_name: str
    ask_metrics_mode: str
    mock: dict[str, bool]
    questions: list[dict[str, Any]]
    notice: str


class ConfigEffectiveResponse(BaseModel):
    version: str
    generated_at: str
    read_only: bool
    provenance: dict[str, Any]
    project: dict[str, Any]
    customer: dict[str, Any]
    dashboard: dict[str, Any]
    capabilities: dict[str, Any]
    mock_switches: dict[str, Any]
    prompt_profiles: dict[str, Any]
    implementation_status: dict[str, Any]
    sensitive: dict[str, Any]


class ConfigSchemaResponse(BaseModel):
    version: str
    generated_at: str
    read_only: bool
    sources: list[str]
    sections: dict[str, Any]
    disabled_endpoints: list[str]


class TtsSynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str | None = Field(default=None, max_length=80)
    format: str | None = Field(default=None, max_length=20)


class TtsSynthesizeResponse(BaseModel):
    success: bool
    audio_url: str | None = None
    audio_id: str | None = None
    duration_ms: int | None = None
    provider: str
    voice: str
    format: str
    mock: bool
    error: ErrorDetail | None = None


class ScreenAction(BaseModel):
    id: str
    label: str
    type: str
    description: str = ""
    fvs_function: str
    params: dict[str, Any] = Field(default_factory=dict)
    speak_text: str

    model_config = ConfigDict(extra="ignore")


class ScreenActionsResponse(BaseModel):
    actions: list[ScreenAction]


class ScreenExecuteRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: f"demo-session-{uuid4().hex[:8]}")
    action_id: str = Field(min_length=1, max_length=100)
    target: str | None = Field(default=None, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)


class AuthorizedScreenAction(BaseModel):
    id: str
    action_id: str
    label: str
    type: str
    description: str = ""
    target: str | None = None
    provider: str
    fvs_function: str
    fvs_routing: dict[str, Any]
    params: dict[str, Any] = Field(default_factory=dict)
    speak_text: str
    validation: dict[str, Any] = Field(default_factory=dict)


class ScreenExecuteResponse(BaseModel):
    success: bool
    action_id: str
    speak_text: str
    target: str | None = None
    provider: str | None = None
    authorized_action: AuthorizedScreenAction | None = None
    resolved_action: AuthorizedScreenAction | None = None
    validation: dict[str, Any] | None = None
    rejection_reason: str | None = None
    request_id: str | None = None
    error: ErrorDetail | None = None


OpsStatus = Literal["ok", "warning", "error", "unknown"]


class OpsHealthResponse(BaseModel):
    status: OpsStatus
    app: str
    version: str
    customer_id: str
    time: str


class OpsDependencyStatus(BaseModel):
    name: str
    label: str
    status: OpsStatus
    latency_ms: int | None = None
    message: str = ""
    checked_at: str
    details: dict[str, Any] = Field(default_factory=dict)


class OpsDependenciesResponse(BaseModel):
    status: OpsStatus
    dependencies: list[OpsDependencyStatus]


class OpsSessionSummary(BaseModel):
    session_id: str
    last_message_at: str
    turns: int
    last_intent_type: str
    last_user_text: str | None = None
    last_error: dict[str, Any] | None = None
    last_latency_ms: int | None = None


class OpsSessionsResponse(BaseModel):
    sessions: list[OpsSessionSummary]


class OpsSessionEvent(BaseModel):
    id: int
    session_id: str
    message_id: str
    created_at: str
    user_text: str | None = None
    intent_type: str
    response_summary: str | None = None
    screen_action: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    latency_total_ms: int


class OpsSessionDetailResponse(BaseModel):
    session_id: str
    events: list[OpsSessionEvent]


class OpsErrorItem(BaseModel):
    id: int
    session_id: str
    message_id: str
    created_at: str
    intent_type: str
    code: str
    message: str
    user_text: str | None = None
    latency_total_ms: int


class OpsErrorsResponse(BaseModel):
    errors: list[OpsErrorItem]


class OpsLatencyBucket(BaseModel):
    name: str
    count: int
    avg_latency_ms: int | None = None
    max_latency_ms: int | None = None
    error_count: int


class OpsLatencySample(BaseModel):
    created_at: str
    session_id: str
    intent_type: str
    latency_total_ms: int


class OpsMetricsResponse(BaseModel):
    total_events: int
    total_sessions: int
    error_events: int
    avg_latency_ms: int | None = None
    p50_latency_ms: int | None = None
    p95_latency_ms: int | None = None
    max_latency_ms: int | None = None
    by_intent: list[OpsLatencyBucket]
    recent_latency: list[OpsLatencySample]
