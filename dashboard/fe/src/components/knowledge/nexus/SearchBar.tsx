'use client';

import React, { useState, useCallback, RefObject } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { QueryMode } from '@/hooks/use-nexus-explorer';
import { FONT } from './typography';
import { Icon } from './Icon';

interface SearchBarProps {
  isLoading: boolean;
  hasQuery: boolean;
  mode: QueryMode;
  onModeChange: (mode: QueryMode) => void;
  onQuery: (q: string, mode: QueryMode, topK: number) => Promise<void>;
  onClear: () => void;
  inputRef?: RefObject<HTMLInputElement | null>;
}

export default function SearchBar({ isLoading, hasQuery, mode, onModeChange, onQuery, onClear, inputRef }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [topK, setTopK] = useState(10);
  const [expanded, setExpanded] = useState(false);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    await onQuery(query.trim(), mode, topK);
  }, [query, mode, topK, onQuery]);

  return (
    <div className="w-full relative">
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 px-3 py-1 rounded-lg border transition-colors w-full"
        style={{
          background: 'var(--color-surface)',
          borderColor: expanded ? 'var(--color-primary)' : 'var(--color-border)',
        }}
      >
        <Icon name="search" size={16} style={{ color: 'var(--color-primary)' }} className="shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setExpanded(true)}
          placeholder="Explore knowledge..."
          className="flex-1 bg-transparent border-none outline-none text-sm"
          style={{ color: 'var(--color-text-main)' }}
        />

        {hasQuery && (
          <button
            type="button"
            onClick={onClear}
            className="p-1 rounded-md hover:bg-black/5 dark:hover:bg-white/10 transition-colors shrink-0 flex items-center justify-center"
            title="Clear results"
          >
            <Icon name="close" size={14} style={{ color: 'var(--color-text-muted)' }} />
          </button>
        )}

        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="p-1 rounded-md hover:bg-black/5 dark:hover:bg-white/10 transition-colors shrink-0 flex items-center justify-center"
        >
          <Icon name={expanded ? 'expand_less' : 'tune'} size={14} style={{ color: 'var(--color-text-muted)' }} />
        </button>

        <button
          type="submit"
          disabled={isLoading || !query.trim()}
          className={`flex items-center gap-1 px-2 py-1 rounded-md ${FONT.body} font-medium text-white transition-all disabled:opacity-40 shrink-0`}
          style={{ background: 'var(--color-primary)' }}
        >
          {isLoading ? (
            <Icon name="progress_activity" size={14} className="animate-spin" />
          ) : (
            <Icon name="arrow_forward" size={14} />
          )}
        </button>
      </form>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, y: -5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full left-0 right-0 mt-2 rounded-xl border shadow-xl overflow-hidden z-50"
            style={{
              background: 'var(--surface-overlay-bg)',
              borderColor: 'var(--color-border)',
              backdropFilter: 'var(--surface-overlay-blur)',
            }}
          >
            <div className="flex items-center gap-3 px-3 py-2.5">
              <div className="flex items-center gap-1.5">
                <span className={`${FONT.caption} font-medium uppercase tracking-wide`} style={{ color: 'var(--color-text-muted)' }}>
                  Mode
                </span>
                <div className="flex gap-1">
                  {(['graph', 'raw', 'summarized'] as QueryMode[]).map(m => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => onModeChange(m)}
                      className={`px-2 py-0.5 rounded ${FONT.label} font-medium border transition-all`}
                      style={{
                        background: mode === m ? 'var(--color-primary-muted)' : 'transparent',
                        borderColor: mode === m ? 'var(--color-primary)' : 'var(--color-border)',
                        color: mode === m ? 'var(--color-primary)' : 'var(--color-text-muted)',
                      }}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-1.5 ml-auto">
                <span className={`${FONT.caption} font-medium uppercase tracking-wide`} style={{ color: 'var(--color-text-muted)' }}>
                  K:{topK}
                </span>
                <input
                  type="range" min={5} max={50} step={5} value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="w-16"
                />
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
