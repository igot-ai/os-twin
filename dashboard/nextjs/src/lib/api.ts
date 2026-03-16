/**
 * Fetch wrapper with auth token injection.
 * Mirrors the originalFetch interceptor from app.js.
 */

function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('agent_os_token');
}

export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token && url.startsWith('/api/')) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  // Show login overlay on 401
  if (response.status === 401 && typeof document !== 'undefined') {
    const overlay = document.getElementById('auth-overlay');
    if (overlay) overlay.style.display = 'flex';
  }

  return response;
}

export async function apiGet<T>(url: string): Promise<T> {
  const res = await apiFetch(url);
  return res.json();
}

export async function apiPost<T>(
  url: string,
  body?: unknown
): Promise<T> {
  const res = await apiFetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

export async function apiPut<T>(
  url: string,
  body?: unknown
): Promise<T> {
  const res = await apiFetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

export async function apiDelete<T>(url: string): Promise<T> {
  const res = await apiFetch(url, {
    method: 'DELETE',
  });
  return res.json();
}
