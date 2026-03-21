/**
 * Fetch wrapper with cookie-based authentication.
 *
 * All API calls include credentials (cookies). On 401, dispatches
 * a custom 'ostwin:auth-required' event to trigger the auth popup.
 */

export async function apiFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Always send cookies
  });

  // On 401, fire custom event so useAuth shows the popup
  if (response.status === 401 && typeof window !== 'undefined') {
    // Don't trigger for auth endpoints themselves
    if (!url.startsWith('/api/auth/')) {
      window.dispatchEvent(new CustomEvent('ostwin:auth-required'));
    }
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
