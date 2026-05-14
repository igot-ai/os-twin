'use client';

import { useEffect, useCallback } from 'react';

interface ShortcutHandlers {
  onFocusSearch: () => void;
  onClearSelection: () => void;
  onReset: () => void;
  onToggleCommunity: () => void;
  onToggleDegree: () => void;
  onToggleLeftDock: () => void;
  onToggleRightDock: () => void;
}

export function useShortcuts({
  onFocusSearch,
  onClearSelection,
  onReset,
  onToggleCommunity,
  onToggleDegree,
  onToggleLeftDock,
  onToggleRightDock,
}: ShortcutHandlers) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) {
      return;
    }

    switch (e.key) {
      case '/':
        e.preventDefault();
        onFocusSearch();
        break;
      case 'Escape':
        onClearSelection();
        break;
      case 'r':
        onReset();
        break;
      case 'c':
        onToggleCommunity();
        break;
      case 'd':
        onToggleDegree();
        break;
      case '[':
        onToggleLeftDock();
        break;
      case ']':
        onToggleRightDock();
        break;
    }
  }, [onFocusSearch, onClearSelection, onReset, onToggleCommunity, onToggleDegree, onToggleLeftDock, onToggleRightDock]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
