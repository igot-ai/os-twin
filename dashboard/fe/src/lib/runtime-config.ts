const browserApiBase = '/api';

function isBrowser(): boolean {
  return globalThis?.window !== undefined;
}

export function getApiBaseUrl(): string {
  // Always prioritize the environment variable if set, even in the browser.
  // This allows overriding the API base for development or testing (e.g. Playwright).
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }

  return browserApiBase;
}

export function getWebSocketUrl(): string {
  if (isBrowser()) {
    return globalThis.window.location.origin.replace(/^http/, 'ws') + '/api/ws';
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:3366/api';
  return apiBase.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws';
}
