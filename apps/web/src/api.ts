import type {
  AsrTranscribeRequest,
  AsrTranscribeResponse,
  ChatRequest,
  ChatResponse,
  ChatStreamTtsReady,
  ScreenActionsResponse,
  ScreenExecuteResponse,
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

  const reader = response.body.getReader();
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
      handleSseFrame(frame, handlers);
      separatorIndex = buffer.indexOf('\n\n');
    }
  }

  buffer += decoder.decode();
  if (buffer.trim()) {
    handleSseFrame(buffer, handlers);
  }
}

function handleSseFrame(frame: string, handlers: ChatStreamHandlers) {
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
  if (event === 'dora_delta') {
    handlers.onDelta?.(payload.text ?? '');
  } else if (event === 'answer') {
    handlers.onAnswer?.(payload as ChatResponse);
  } else if (event === 'tts_ready') {
    handlers.onTtsReady?.(payload as ChatStreamTtsReady);
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

export function synthesizeSpeech(payload: TtsSynthesizeRequest): Promise<TtsSynthesizeResponse> {
  return requestJson<TtsSynthesizeResponse>('/api/tts', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
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
