const browserApiBase = '/api';

function isBrowser(): boolean {
  return globalThis !== undefined && globalThis.window !== undefined;
}

export function getApiBaseUrl(): string {
  if (isBrowser()) {
    return browserApiBase;
  }

  return process.env.NEXT_PUBLIC_API_BASE_URL || browserApiBase;
}

export function getWebSocketUrl(): string {
  if (isBrowser()) {
    return globalThis.window.location.origin.replace(/^http/, 'ws') + '/api/ws';
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:9000/api';
  return apiBase.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws';
}
