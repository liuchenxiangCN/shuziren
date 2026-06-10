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
}

export interface WakeConfigResponse {
  version: string;
  mode: string;
  wake_words: string[];
  settings: WakeSettings;
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
  request_id?: string | null;
  error?: ErrorDetail | null;
}
