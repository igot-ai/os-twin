'use client';

import { useEffect } from 'react';
import { useUIStore } from '@/lib/stores/uiStore';

export const KeyboardShortcutManager = () => {
  const { 
    toggleTheme, 
    toggleSidebar, 
    setHelpModalOpen, 
    setSearchModalOpen
  } = useUIStore();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Check if user is typing in an input
      const target = e.target as HTMLElement;
      const isInput = target.tagName === 'INPUT' || 
                      target.tagName === 'TEXTAREA' || 
                      target.isContentEditable;
      
      if (isInput) return;

      // Cmd+K or Ctrl+K for Search
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setSearchModalOpen(true);
      }

      // '?' for Help (requires shift)
      if (e.key === '?') {
        e.preventDefault();
        setHelpModalOpen(true);
      }

      // 'T' for Theme Toggle
      if (e.key.toLowerCase() === 't') {
        e.preventDefault();
        toggleTheme();
      }

      // '[' for Sidebar Toggle
      if (e.key === '[') {
        e.preventDefault();
        toggleSidebar();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [toggleTheme, toggleSidebar, setHelpModalOpen, setSearchModalOpen]);

  return null;
};
