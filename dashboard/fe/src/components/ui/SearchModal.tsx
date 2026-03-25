'use client';

import React, { useState } from 'react';
import { Modal } from './Modal';
import { useUIStore } from '@/lib/stores/uiStore';

export const SearchModal = () => {
  const { searchModalOpen, setSearchModalOpen } = useUIStore();
  const [query, setQuery] = useState('');

  return (
    <Modal
      isOpen={searchModalOpen}
      onClose={() => setSearchModalOpen(false)}
      title="Search Command Center"
      size="lg"
    >
      <div className="space-y-4">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-faint">
            search
          </span>
          <input
            autoFocus
            type="text"
            placeholder="Search plans, EPICs, tasks..."
            className="w-full pl-10 pr-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary text-text-main"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            role="searchbox"
            aria-label="Search input"
          />
        </div>

        <div className="py-8 text-center">
          <div className="w-16 h-16 bg-surface-hover rounded-2xl flex items-center justify-center mx-auto mb-4">
            <span className="material-symbols-outlined text-3xl text-text-faint">
              manage_search
            </span>
          </div>
          <p className="text-sm font-bold text-text-main">Global Search</p>
          <p className="text-xs text-text-muted max-w-[280px] mx-auto mt-1">
            Search across all plans, agent logs, and system configurations.
          </p>
        </div>

        <div className="pt-4 border-t border-border flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
              <kbd className="px-1 py-0.5 rounded border border-border bg-background shadow-sm font-mono">↑↓</kbd>
              <span>to navigate</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
              <kbd className="px-1 py-0.5 rounded border border-border bg-background shadow-sm font-mono">↵</kbd>
              <span>to select</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
            <kbd className="px-1 py-0.5 rounded border border-border bg-background shadow-sm font-mono">esc</kbd>
            <span>to close</span>
          </div>
        </div>
      </div>
    </Modal>
  );
};
