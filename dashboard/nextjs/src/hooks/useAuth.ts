'use client';

import { useState, useCallback, useEffect } from 'react';

export function useAuth() {
  const [showLogin, setShowLogin] = useState(false);
  const [error, setError] = useState('');
  const [checking, setChecking] = useState(true);

  // On mount, check if we already have a valid session (cookie)
  useEffect(() => {
    let cancelled = false;

    async function checkAuth() {
      try {
        // Try /api/auth/me — if cookie is valid, this returns 200
        const res = await fetch('/api/auth/me', { credentials: 'include' });
        if (res.ok) {
          // Already authenticated via cookie
          if (!cancelled) setChecking(false);
          return;
        }
      } catch {
        // Network error — continue to try local-key
      }

      // No valid cookie — try fetching local-key
      try {
        const res = await fetch('/api/auth/local-key');
        if (res.ok) {
          const data = await res.json();
          if (data?.key) {
            // Auto-authenticate: POST to /token to set the cookie
            const tokenRes = await fetch('/api/auth/token', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ key: data.key }),
              credentials: 'include',
            });
            if (tokenRes.ok) {
              // Cookie is now set — good to go
              if (!cancelled) setChecking(false);
              return;
            }
          }
        }
      } catch {
        // Can't reach local-key
      }

      // No valid session and can't auto-auth — show login popup
      if (!cancelled) {
        setChecking(false);
        setShowLogin(true);
      }
    }

    checkAuth();
    return () => { cancelled = true; };
  }, []);

  // Listen for 401 events from apiFetch
  useEffect(() => {
    const handler = () => setShowLogin(true);
    window.addEventListener('ostwin:auth-required', handler);
    return () => window.removeEventListener('ostwin:auth-required', handler);
  }, []);

  const performLogin = useCallback(async (apiKey: string) => {
    if (!apiKey.trim()) {
      setError('Please enter your API key.');
      return false;
    }

    try {
      const res = await fetch('/api/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: apiKey.trim() }),
        credentials: 'include',
      });

      if (!res.ok) {
        setError('Invalid API key. Check your key and try again.');
        return false;
      }

      // Cookie is set by the backend response
      setShowLogin(false);
      setError('');
      // Reload to re-fetch all data with valid cookie
      window.location.reload();
      return true;
    } catch {
      setError('Network error. Is the dashboard running?');
      return false;
    }
  }, []);

  return { showLogin, setShowLogin, error, performLogin, checking };
}
