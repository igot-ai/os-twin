'use client';

import { useState, useEffect, useCallback } from 'react';

export function useDockState(side: 'left' | 'right') {
  const key = `nexus-dock-${side}`;
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    try {
      return localStorage.getItem(key) === 'true';
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, String(collapsed));
    } catch {}
  }, [key, collapsed]);

  const toggle = useCallback(() => setCollapsed(prev => !prev), []);

  return { collapsed, toggle };
}
