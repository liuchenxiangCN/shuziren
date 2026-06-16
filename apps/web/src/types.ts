export type ChatType = 'answer' | 'screen_control' | 'clarify' | 'fallback';

export interface ErrorDetail {
  code: string;
  message: string;
}

export interface ChatRequest {
  session_id: string;
  text: string;
  context: Record<string, unknown>;
}

export interface ScreenControlAction {
  id: string;
  target?: string | null;
}

export interface ChatResponse {
  session_id: string;
  message_id: string;
  type: ChatType;
  speak_text: string;
  title?: string | null;
  display?: {
    mode?: string;
    summary?: string;
    bullets?: string[];
    chart_config?: Record<string, unknown>;
  } | null;
  action?: ScreenControlAction | null;
  reason?: string | null;
  error?: ErrorDetail | null;
}

export interface ChatStreamTtsReady {
  index: number;
  text: string;
  audio_url: string;
  audio_id?: string | null;
  duration_ms?: number | null;
  provider: string;
  format: string;
  mock: boolean;
}

export interface TtsStreamMetadata {
  provider: string;
  voice: string;
  format: string;
  mime_type: string;
  sample_rate: number;
  mock: boolean;
  fallback?: string;
}

export interface TtsStreamAudioChunk {
  index: number;
  audio_base64: string;
  mime_type: string;
  provider: string;
  format: string;
  sample_rate: number;
  duration_ms?: number | null;
  mock: boolean;
}

export interface TtsStreamEnd {
  ok: boolean;
  chunks: number;
  duration_ms?: number | null;
  fallback?: string;
}

export interface ScreenAction {
  id: string;
  label: string;
  type: string;
  description: string;
  fvs_function: string;
  params: Record<string, unknown>;
  speak_text: string;
}

export interface ScreenActionsResponse {
  actions: ScreenAction[];
}

export interface AuthorizedScreenAction extends ScreenAction {
  action_id: string;
  target?: string | null;
  provider: string;
  fvs_routing: Record<string, unknown>;
  validation: Record<string, unknown>;
}

export interface AsrTranscribeRequest {
  session_id: string;
  mock_text?: string | null;
  audio_base64?: string | null;
  audio_format?: string | null;
}

export interface AsrTranscribeResponse {
  success: boolean;
  session_id: string;
  text: string;
  provider: string;
  mock: boolean;
  duration_ms?: number | null;
  error?: ErrorDetail | null;
}

export interface WakeSettings {
  min_audio_ms: number;
  max_audio_ms: number;
  cooldown_ms: number;
  require_exact_phrase: boolean;
  vad_threshold: number;
  silence_ms: number;
  command_timeout_ms: number;
  followup_enabled: boolean;
  followup_window_ms: number;
  max_followup_turns: number;
  barge_in_enabled: boolean;
  barge_in_wake_words: string[];
  barge_in_vad_threshold: number;
  barge_in_min_audio_ms: number;
  barge_in_silence_ms: number;
  barge_in_max_audio_ms: number;
  barge_in_ignore_after_tts_start_ms: number;
}

export interface WakeConfigResponse {
  version: string;
  mode: string;
  wake_words: string[];
  settings: WakeSettings;
}

export interface DemoQuestion {
  id?: string;
  text?: string;
  category?: string;
  expected?: string;
}

export interface DemoConfigResponse {
  stable_mode: boolean;
  project_id: string;
  project_name: string;
  product_name: string;
  customer_id: string;
  customer_name: string;
  scenario_name: string;
  assistant_name: string;
  ask_metrics_mode: string;
  mock: Record<string, boolean>;
  questions: DemoQuestion[];
  notice: string;
}

export interface ConfigField<T = unknown> {
  value?: T;
  source?: string;
  sensitive?: boolean;
  notes?: string;
  status?: string;
  configured?: boolean;
  masked?: string;
  label?: string;
}

export type ConfigSection = Record<string, unknown>;

export interface ConfigEffectiveResponse {
  version: string;
  generated_at: string;
  read_only: boolean;
  provenance: ConfigSection;
  project: Record<string, ConfigField>;
  customer: Record<string, ConfigField>;
  dashboard: ConfigSection;
  capabilities: ConfigSection;
  mock_switches: Record<string, ConfigField>;
  prompt_profiles: ConfigSection;
  implementation_status: Record<string, string>;
  sensitive: Record<string, ConfigField>;
}

export interface ConfigSchemaResponse {
  version: string;
  generated_at: string;
  read_only: boolean;
  sources: string[];
  sections: ConfigSection;
  disabled_endpoints: string[];
  enabled_endpoints: string[];
  writable: ConfigSection;
}

export interface ConfigOverridePayload {
  overrides: Record<string, unknown>;
  operator?: string | null;
  reason?: string | null;
}

export interface ConfigOverrideResponse {
  version: number;
  path: string;
  exists: boolean;
  updated_at?: string | null;
  updated_by?: string | null;
  reason?: string | null;
  sha256: string;
  access: Record<string, unknown>;
  overrides: Record<string, unknown>;
}

export interface ConfigValidateResponse {
  ok: boolean;
  dry_run: boolean;
  summary: Record<string, unknown>;
  errors: Array<Record<string, unknown>>;
  warnings: Array<Record<string, unknown>>;
  normalized_overrides: Record<string, unknown>;
  effective_preview: Record<string, unknown>;
  action_preview: Array<Record<string, unknown>>;
}

export interface ConfigReloadResponse {
  success: boolean;
  reloaded_at: string;
  summary: Record<string, unknown>;
  error?: ErrorDetail | null;
}

export interface ConfigAuditEvent {
  event_id: string;
  created_at: string;
  operator: string;
  action: string;
  reason: string;
  ok: boolean;
  summary: Record<string, unknown>;
  errors: Array<Record<string, unknown>>;
  active_sha256?: string | null;
}

export interface ConfigAuditResponse {
  events: ConfigAuditEvent[];
}

export interface TtsSynthesizeRequest {
  text: string;
  voice?: string | null;
  format?: string | null;
}

export interface TtsSynthesizeResponse {
  success: boolean;
  audio_url?: string | null;
  audio_id?: string | null;
  duration_ms?: number | null;
  provider: string;
  voice: string;
  format: string;
  mock: boolean;
  error?: ErrorDetail | null;
}

export interface ScreenExecuteResponse {
  success: boolean;
  action_id: string;
  speak_text: string;
  target?: string | null;
  provider?: string | null;
  authorized_action?: AuthorizedScreenAction | null;
  resolved_action?: AuthorizedScreenAction | null;
  validation?: Record<string, unknown> | null;
  rejection_reason?: string | null;
  request_id?: string | null;
  error?: ErrorDetail | null;
}

export type OpsStatus = 'ok' | 'warning' | 'error' | 'unknown';

export interface OpsHealthResponse {
  status: OpsStatus;
  app: string;
  version: string;
  customer_id: string;
  time: string;
}

export interface OpsDependencyStatus {
  name: string;
  label: string;
  status: OpsStatus;
  latency_ms?: number | null;
  message: string;
  checked_at: string;
  details: Record<string, unknown>;
}

export interface OpsDependenciesResponse {
  status: OpsStatus;
  dependencies: OpsDependencyStatus[];
}

export interface OpsSessionSummary {
  session_id: string;
  last_message_at: string;
  turns: number;
  last_intent_type: string;
  last_user_text?: string | null;
  last_error?: Record<string, unknown> | null;
  last_latency_ms?: number | null;
}

export interface OpsSessionsResponse {
  sessions: OpsSessionSummary[];
}

export interface OpsErrorItem {
  id: number;
  session_id: string;
  message_id: string;
  created_at: string;
  intent_type: string;
  code: string;
  message: string;
  user_text?: string | null;
  latency_total_ms: number;
}

export interface OpsErrorsResponse {
  errors: OpsErrorItem[];
}

export interface OpsLatencyBucket {
  name: string;
  count: number;
  avg_latency_ms?: number | null;
  max_latency_ms?: number | null;
  error_count: number;
}

export interface OpsLatencySample {
  created_at: string;
  session_id: string;
  intent_type: string;
  latency_total_ms: number;
}

export interface OpsMetricsResponse {
  total_events: number;
  total_sessions: number;
  error_events: number;
  avg_latency_ms?: number | null;
  p50_latency_ms?: number | null;
  p95_latency_ms?: number | null;
  max_latency_ms?: number | null;
  by_intent: OpsLatencyBucket[];
  recent_latency: OpsLatencySample[];
}
