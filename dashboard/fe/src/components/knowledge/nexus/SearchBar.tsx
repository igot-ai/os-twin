'use client';

import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { QueryMode } from '@/hooks/use-nexus-explorer';

interface SearchBarProps {
  isLoading: boolean;
  hasQuery: boolean;
  onQuery: (q: string, mode: QueryMode, topK: number) => Promise<void>;
  onClear: () => void;
}

export default function SearchBar({ isLoading, hasQuery, onQuery, onClear }: SearchBarProps) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<QueryMode>('graph');
  const [topK, setTopK] = useState(10);
  const [expanded, setExpanded] = useState(false);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    await onQuery(query.trim(), mode, topK);
  }, [query, mode, topK, onQuery]);

  return (
    <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 w-full max-w-[620px] px-3">
      <form
        onSubmit={handleSubmit}
        className="rounded-xl border shadow-2xl overflow-hidden"
        style={{
          background: 'rgba(255, 255, 255, 0.92)',
          borderColor: expanded ? 'var(--color-primary)' : 'var(--color-border)',
          backdropFilter: 'blur(16px)',
          transition: 'border-color 0.2s',
        }}
      >
        <div className="flex items-center gap-2 px-3 py-2.5">
          <span className="material-symbols-outlined text-[18px] shrink-0" style={{ color: 'var(--color-primary)' }}>
            search
          </span>
          <input
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
              className="p-1 rounded-md hover:bg-white/10 transition-colors shrink-0"
              title="Clear results"
            >
              <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-text-muted)' }}>close</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="p-1 rounded-md hover:bg-white/10 transition-colors shrink-0"
          >
            <span className="material-symbols-outlined text-[16px]" style={{ color: 'var(--color-text-muted)' }}>
              {expanded ? 'expand_less' : 'tune'}
            </span>
          </button>

          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-semibold text-white transition-all disabled:opacity-40 shrink-0"
            style={{ background: 'var(--color-primary)' }}
          >
            {isLoading ? (
              <span className="material-symbols-outlined text-[14px] animate-spin">progress_activity</span>
            ) : (
              <span className="material-symbols-outlined text-[14px]">arrow_forward</span>
            )}
          </button>
        </div>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="overflow-hidden"
            >
              <div
                className="flex items-center gap-3 px-3 py-2 border-t"
                style={{ borderColor: 'var(--color-border)' }}
              >
                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
                    Mode
                  </span>
                  <div className="flex gap-1">
                    {(['graph', 'raw', 'summarized'] as QueryMode[]).map(m => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setMode(m)}
                        className="px-2 py-0.5 rounded text-[10px] font-medium border transition-all"
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

                <div className="flex items-center gap-1.5">
                  <span className="text-[9px] font-medium uppercase tracking-wide" style={{ color: 'var(--color-text-muted)' }}>
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
      </form>
    </div>
  );
}
