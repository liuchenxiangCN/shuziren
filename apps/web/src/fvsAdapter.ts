import type { ScreenAction } from './types';

export type FvsIntegrationMode = 'mock' | 'iframe' | 'parent';

export interface FvsConfig {
  enabled: boolean;
  mode: FvsIntegrationMode;
  url: string;
  targetOrigin: string;
}

export interface FvsActionResult {
  success: boolean;
  mode: FvsIntegrationMode;
  message: string;
}

interface FvsActionMessage {
  type: 'FVS_ACTION';
  source: 'configurable-digital-human';
  action_id: string;
  actionId: string;
  functionName: string;
  params: Record<string, unknown>;
}

const PLACEHOLDER_URLS = new Set(['https://your-fvs-url', 'http://your-fvs-url']);

export function getFvsConfig(): FvsConfig {
  const runtime = getRuntimeConfig();
  const url = normalizeUrl(runtime.url || import.meta.env.VITE_FVS_URL);
  const mode = normalizeMode(runtime.mode || import.meta.env.VITE_FVS_INTEGRATION_MODE || (url ? 'iframe' : 'mock'));
  const targetOrigin = resolveTargetOrigin(url, runtime.targetOrigin || import.meta.env.VITE_FVS_TARGET_ORIGIN);
  const enabled = mode !== 'mock' && (mode === 'parent' || Boolean(url));
  return {
    enabled,
    mode: enabled ? mode : 'mock',
    url,
    targetOrigin,
  };
}

export function executeFvsAction(
  action: ScreenAction,
  config: FvsConfig,
  iframe?: HTMLIFrameElement | null,
): FvsActionResult {
  if (!config.enabled || config.mode === 'mock') {
    return {
      success: true,
      mode: 'mock',
      message: 'Mock FVS action applied locally.',
    };
  }

  const message: FvsActionMessage = {
    type: 'FVS_ACTION',
    source: 'configurable-digital-human',
    action_id: action.id,
    actionId: action.id,
    functionName: action.fvs_function,
    params: action.params,
  };

  try {
    if (config.mode === 'iframe') {
      if (!iframe) {
        return {
          success: false,
          mode: config.mode,
          message: 'FVS iframe is not ready.',
        };
      }
      const pageNumber = getPageNumber(action);
      if (pageNumber !== null) {
        iframe.src = buildPageUrl(iframe.getAttribute('src') || config.url, pageNumber);
        return {
          success: true,
          mode: config.mode,
          message: `FVS iframe navigated to page_number=${pageNumber}.`,
        };
      }
      iframe.contentWindow?.postMessage(message, config.targetOrigin);
      return {
        success: true,
        mode: config.mode,
        message: `postMessage sent to ${config.targetOrigin}.`,
      };
    }

    if (window.parent === window) {
      return {
        success: false,
        mode: config.mode,
        message: 'No parent FVS window is available.',
      };
    }
    window.parent.postMessage(message, config.targetOrigin);
    return {
      success: true,
      mode: config.mode,
      message: `postMessage sent to parent ${config.targetOrigin}.`,
    };
  } catch (error) {
    return {
      success: false,
      mode: config.mode,
      message: error instanceof Error ? error.message : 'FVS postMessage failed.',
    };
  }
}

function getPageNumber(action: ScreenAction): number | null {
  const raw = action.params.pageNumber ?? action.params.page_number;
  const pageNumber = Number(raw);
  if (!Number.isInteger(pageNumber) || pageNumber < 1) {
    return null;
  }
  return pageNumber;
}

function buildPageUrl(currentUrl: string, pageNumber: number): string {
  try {
    const url = new URL(currentUrl, window.location.href);
    url.searchParams.set('page_number', String(pageNumber));
    url.searchParams.delete('page');
    return url.toString();
  } catch {
    const separator = currentUrl.includes('?') ? '&' : '?';
    return `${currentUrl}${separator}page_number=${pageNumber}`;
  }
}

function getRuntimeConfig() {
  if (typeof window === 'undefined') {
    return { mode: '', url: '', targetOrigin: '' };
  }
  const params = new URLSearchParams(window.location.search);
  return {
    mode: params.get('fvs_mode') || params.get('fvsMode') || '',
    url: params.get('fvs_url') || params.get('fvsUrl') || '',
    targetOrigin: params.get('fvs_origin') || params.get('fvsOrigin') || '',
  };
}

function normalizeMode(value: unknown): FvsIntegrationMode {
  const raw = String(value || 'mock').trim().toLowerCase();
  if (raw === 'iframe') return 'iframe';
  if (
    raw === 'parent' ||
    raw === 'parent-postmessage' ||
    raw === 'postmessage' ||
    raw === 'web-frame' ||
    raw === 'webframe' ||
    raw === 'fvs-web-frame'
  ) {
    return 'parent';
  }
  return 'mock';
}

function normalizeUrl(value: unknown): string {
  const url = String(value || '').trim();
  if (!url || PLACEHOLDER_URLS.has(url)) return '';
  return url;
}

function resolveTargetOrigin(url: string, configuredOrigin: unknown): string {
  const targetOrigin = String(configuredOrigin || '').trim();
  if (targetOrigin) return targetOrigin;
  if (!url) return '*';
  try {
    const baseUrl = typeof window === 'undefined' ? 'http://localhost' : window.location.href;
    return new URL(url, baseUrl).origin;
  } catch {
    return '*';
  }
}
