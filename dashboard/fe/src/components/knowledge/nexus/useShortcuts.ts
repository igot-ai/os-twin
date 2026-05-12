'use client';

import { useEffect, useCallback } from 'react';

interface ShortcutHandlers {
  onFocusSearch: () => void;
  onClearSelection: () => void;
  onReset: () => void;
  onSetLens: (lens: 'structural' | 'semantic' | 'category') => void;
  onToggleLeftDock: () => void;
  onToggleRightDock: () => void;
}

export function useShortcuts({
  onFocusSearch,
  onClearSelection,
  onReset,
  onSetLens,
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
      case '1':
        onSetLens('structural');
        break;
      case '2':
        onSetLens('semantic');
        break;
      case '3':
        onSetLens('category');
        break;
      case '[':
        onToggleLeftDock();
        break;
      case ']':
        onToggleRightDock();
        break;
    }
  }, [onFocusSearch, onClearSelection, onReset, onSetLens, onToggleLeftDock, onToggleRightDock]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}
