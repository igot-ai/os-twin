const browserApiBase = '/api';

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    return browserApiBase;
  }

  return process.env.NEXT_PUBLIC_API_BASE_URL || browserApiBase;
}

export function getWebSocketUrl(): string {
  if (typeof window !== 'undefined') {
    return window.location.origin.replace(/^http/, 'ws') + '/api/ws';
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:9000/api';
  return apiBase.replace(/^http/, 'ws').replace(/\/$/, '') + '/ws';
}
