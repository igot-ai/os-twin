'use client';

import { useState, useCallback } from 'react';

export function useAuth() {
  const [showLogin, setShowLogin] = useState(false);
  const [error, setError] = useState('');

  const performLogin = useCallback(async (username: string, password: string) => {
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    try {
      const res = await fetch('/api/auth/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
      });

      if (!res.ok) {
        setError('Login failed. Check credentials.');
        return false;
      }

      const data = await res.json();
      localStorage.setItem('agent_os_token', data.access_token);
      setShowLogin(false);
      setError('');
      return true;
    } catch {
      setError('Network error during login.');
      return false;
    }
  }, []);

  return { showLogin, setShowLogin, error, performLogin };
}
