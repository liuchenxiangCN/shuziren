import type {
  AsrTranscribeRequest,
  AsrTranscribeResponse,
  ChatRequest,
  ChatResponse,
  ChatStreamTtsReady,
  ConfigEffectiveResponse,
  ConfigSchemaResponse,
  DemoConfigResponse,
  OpsDependenciesResponse,
  OpsErrorsResponse,
  OpsHealthResponse,
  OpsMetricsResponse,
  OpsSessionsResponse,
  ScreenActionsResponse,
  ScreenExecuteResponse,
  TtsStreamAudioChunk,
  TtsStreamEnd,
  TtsStreamMetadata,
  TtsSynthesizeRequest,
  TtsSynthesizeResponse,
  WakeConfigResponse,
} from './types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:18080').replace(
  /\/$/,
  '',
);

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  const payload = await response.json();
  if (!response.ok) {
    const message = payload?.error?.message || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload as T;
}

export function fetchScreenActions(): Promise<ScreenActionsResponse> {
  return requestJson<ScreenActionsResponse>('/api/screen/actions');
}

export function sendChat(payload: ChatRequest): Promise<ChatResponse> {
  return requestJson<ChatResponse>('/api/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export interface ChatStreamHandlers {
  onDelta?: (text: string) => void;
  onAnswer?: (response: ChatResponse) => void;
  onTtsReady?: (segment: ChatStreamTtsReady) => void;
  onTtsError?: (payload: { index?: number; message?: string }) => void;
}

export async function streamChat(payload: ChatRequest, handlers: ChatStreamHandlers = {}): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    const errorPayload = await response.json().catch(() => null);
    throw new Error(errorPayload?.error?.message || `HTTP ${response.status}`);
  }

  await readSseStream(response.body, (event, eventPayload) => {
    handleChatSsePayload(event, eventPayload, handlers);
  });
}

async function readSseStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: string, payload: Record<string, unknown>) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex = buffer.indexOf('\n\n');
    while (separatorIndex >= 0) {
      const frame = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      handleSseFrame(frame, onEvent);
      separatorIndex = buffer.indexOf('\n\n');
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    handleSseFrame(buffer, onEvent);
  }
}

function handleSseFrame(frame: string, onEvent: (event: string, payload: Record<string, unknown>) => void) {
  const lines = frame.split(/\r?\n/);
  let event = 'message';
  const dataLines: string[] = [];
  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart());
    }
  }
  if (!dataLines.length) return;

  const payload = JSON.parse(dataLines.join('\n'));
  onEvent(event, payload);
}

function handleChatSsePayload(event: string, payload: Record<string, unknown>, handlers: ChatStreamHandlers) {
  if (event === 'dora_delta') {
    handlers.onDelta?.(String(payload.text ?? ''));
  } else if (event === 'answer') {
    handlers.onAnswer?.(payload as unknown as ChatResponse);
  } else if (event === 'tts_ready') {
    handlers.onTtsReady?.(payload as unknown as ChatStreamTtsReady);
  } else if (event === 'tts_error') {
    handlers.onTtsError?.(payload);
  }
}

export function transcribeAudio(payload: AsrTranscribeRequest): Promise<AsrTranscribeResponse> {
  return requestJson<AsrTranscribeResponse>('/api/asr/transcribe', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchWakeConfig(): Promise<WakeConfigResponse> {
  return requestJson<WakeConfigResponse>('/api/wake/config');
}

export function fetchDemoConfig(): Promise<DemoConfigResponse> {
  return requestJson<DemoConfigResponse>('/api/demo/config');
}

export function fetchConfigEffective(): Promise<ConfigEffectiveResponse> {
  return requestJson<ConfigEffectiveResponse>('/api/config/effective');
}

export function fetchConfigSchema(): Promise<ConfigSchemaResponse> {
  return requestJson<ConfigSchemaResponse>('/api/config/schema');
}

export function synthesizeSpeech(payload: TtsSynthesizeRequest): Promise<TtsSynthesizeResponse> {
  return requestJson<TtsSynthesizeResponse>('/api/tts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export interface TtsStreamHandlers {
  onMetadata?: (metadata: TtsStreamMetadata) => void;
  onAudioChunk?: (chunk: TtsStreamAudioChunk) => void;
  onTtsError?: (payload: { code?: string; message?: string; fallback?: string }) => void;
  onEnd?: (payload: TtsStreamEnd) => void;
}

export async function streamSpeech(
  payload: TtsSynthesizeRequest,
  handlers: TtsStreamHandlers = {},
): Promise<TtsStreamEnd> {
  const response = await fetch(`${API_BASE_URL}/api/tts/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok || !response.body) {
    const errorPayload = await response.json().catch(() => null);
    throw new Error(errorPayload?.error?.message || `HTTP ${response.status}`);
  }

  let endPayload: TtsStreamEnd | null = null;
  await readSseStream(response.body, (event, eventPayload) => {
    if (event === 'metadata') {
      handlers.onMetadata?.(eventPayload as unknown as TtsStreamMetadata);
    } else if (event === 'audio_chunk') {
      handlers.onAudioChunk?.(eventPayload as unknown as TtsStreamAudioChunk);
    } else if (event === 'tts_error') {
      handlers.onTtsError?.(eventPayload);
    } else if (event === 'end') {
      endPayload = eventPayload as unknown as TtsStreamEnd;
      handlers.onEnd?.(endPayload);
    }
  });

  return endPayload ?? { ok: false, chunks: 0 };
}

export function toApiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) {
    return path;
  }
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
}

export function executeScreenAction(payload: {
  session_id: string;
  action_id: string;
  params?: Record<string, unknown>;
}): Promise<ScreenExecuteResponse> {
  return requestJson<ScreenExecuteResponse>('/api/screen/execute', {
    method: 'POST',
    body: JSON.stringify({ ...payload, params: payload.params ?? {} }),
  });
}

export function fetchOpsHealth(): Promise<OpsHealthResponse> {
  return requestJson<OpsHealthResponse>('/api/ops/health');
}

export function fetchOpsDependencies(): Promise<OpsDependenciesResponse> {
  return requestJson<OpsDependenciesResponse>('/api/ops/dependencies');
}

export function fetchOpsSessions(limit = 20): Promise<OpsSessionsResponse> {
  return requestJson<OpsSessionsResponse>(`/api/ops/sessions?limit=${encodeURIComponent(limit)}`);
}

export function fetchOpsErrors(limit = 30): Promise<OpsErrorsResponse> {
  return requestJson<OpsErrorsResponse>(`/api/ops/errors?limit=${encodeURIComponent(limit)}`);
}

export function fetchOpsMetrics(): Promise<OpsMetricsResponse> {
  return requestJson<OpsMetricsResponse>('/api/ops/metrics');
}

export async function fetchOpsExport(limit = 50): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/api/ops/export?limit=${encodeURIComponent(limit)}`, {
    headers: {
      Accept: 'text/markdown',
    },
  });
  if (!response.ok) {
    const errorPayload = await response.json().catch(() => null);
    throw new Error(errorPayload?.error?.message || `HTTP ${response.status}`);
  }
  return response.text();
}
