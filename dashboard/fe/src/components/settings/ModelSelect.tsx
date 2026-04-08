'use client';

import { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import type { ModelInfo, ConfiguredProvider } from '@/types/settings';

const TIER_COLORS: Record<string, string> = {
  flagship: 'bg-amber-100 text-amber-800',
  balanced: 'bg-blue-100 text-blue-800',
  fast: 'bg-emerald-100 text-emerald-800',
  reasoning: 'bg-purple-100 text-purple-800',
  unknown: 'bg-slate-100 text-slate-500',
};

const SOURCE_BADGE: Record<string, { label: string; cls: string }> = {
  'models.dev': { label: 'catalog', cls: 'bg-sky-50 text-sky-600 border-sky-200' },
  custom:       { label: 'custom',  cls: 'bg-amber-50 text-amber-600 border-amber-200' },
};

export interface ModelSelectProps {
  value: string;
  onChange: (modelId: string) => void;
  models: ModelInfo[];
  providers?: Record<string, ConfiguredProvider>;
  disabled?: boolean;
  placeholder?: string;
  /** @deprecated ignored -- always renders the searchable dropdown */
  grouped?: boolean;
  showTier?: boolean;
  showContext?: boolean;
  className?: string;
}

export function ModelSelect({
  value,
  onChange,
  models,
  providers,
  disabled = false,
  placeholder = 'Select model',
  showTier = true,
  showContext = true,
  className = '',
}: ModelSelectProps) {
  const [search, setSearch] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // ── Group models by provider ─────────────────────────────────────
  const groupedModels = useMemo(() => {
    const groups: Record<string, {
      name: string;
      logo_url: string;
      models: ModelInfo[];
    }> = {};

    for (const model of models) {
      const pid = model.provider_id || '_other';
      if (!groups[pid]) {
        const prov = providers?.[pid];
        groups[pid] = {
          name: prov?.name || pid,
          logo_url: model.logo_url || `https://models.dev/logos/${pid}.svg`,
          models: [],
        };
      }
      groups[pid].models.push(model);
    }
    return groups;
  }, [models, providers]);

  // ── Filter ───────────────────────────────────────────────────────
  const { filteredGroups, flatFiltered } = useMemo(() => {
    const q = search.trim().toLowerCase();
    const fg: typeof groupedModels = {};
    const flat: ModelInfo[] = [];

    for (const [pid, group] of Object.entries(groupedModels)) {
      // If the search matches the provider name, show all its models
      const providerMatch = q && group.name.toLowerCase().includes(q);

      const matched = group.models.filter(
        (m) =>
          !q ||
          providerMatch ||
          m.id.toLowerCase().includes(q) ||
          (m.label || '').toLowerCase().includes(q) ||
          (m.family || '').toLowerCase().includes(q),
      );

      if (matched.length > 0) {
        fg[pid] = { ...group, models: matched };
        flat.push(...matched);
      }
    }
    return { filteredGroups: fg, flatFiltered: flat };
  }, [groupedModels, search]);

  // Reset highlight when list changes
  useEffect(() => { setHighlightIdx(-1); }, [flatFiltered.length]);

  // ── Keyboard navigation ──────────────────────────────────────────
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) {
        if (e.key === 'ArrowDown' || e.key === 'Enter') {
          e.preventDefault();
          setIsOpen(true);
        }
        return;
      }
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setHighlightIdx((i) => Math.min(i + 1, flatFiltered.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setHighlightIdx((i) => Math.max(i - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (highlightIdx >= 0 && highlightIdx < flatFiltered.length) {
            onChange(flatFiltered[highlightIdx].id);
            close();
          }
          break;
        case 'Escape':
          e.preventDefault();
          close();
          break;
      }
    },
    [isOpen, highlightIdx, flatFiltered, onChange],
  );

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightIdx < 0 || !listRef.current) return;
    const el = listRef.current.querySelector(`[data-idx="${highlightIdx}"]`);
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlightIdx]);

  const close = () => {
    setIsOpen(false);
    setSearch('');
    setHighlightIdx(-1);
  };

  const open = () => {
    if (disabled) return;
    setIsOpen(true);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  // ── Selected model display ───────────────────────────────────────
  const selected = models.find((m) => m.id === value);

  // Build a running index for keyboard nav
  let runIdx = 0;

  return (
    <div className={`relative ${className}`} onKeyDown={handleKeyDown}>
      {/* ── Trigger ─────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={() => (isOpen ? close() : open())}
        disabled={disabled}
        className="w-full bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5 text-sm text-left flex items-center gap-2 hover:bg-white hover:border-slate-300 transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400"
      >
        {selected ? (
          <>
            {selected.provider_id && (
              <img
                src={`https://models.dev/logos/${selected.provider_id}.svg`}
                alt=""
                className="w-4 h-4 flex-shrink-0"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            )}
            <span className="font-mono text-slate-900 truncate text-xs">{selected.label || selected.id}</span>
            {selected.source && (
              <span className={`text-[8px] font-bold uppercase px-1 py-px rounded border flex-shrink-0 ${SOURCE_BADGE[selected.source]?.cls || SOURCE_BADGE.custom.cls}`}>
                {SOURCE_BADGE[selected.source]?.label || selected.source}
              </span>
            )}
            {showContext && selected.context_window && (
              <span className="text-[10px] text-slate-400 ml-auto flex-shrink-0">{selected.context_window}</span>
            )}
          </>
        ) : (
          <span className="text-slate-400 text-xs">{placeholder}</span>
        )}
        <span className="material-symbols-outlined text-slate-400 ml-auto flex-shrink-0 text-base">
          {isOpen ? 'expand_less' : 'expand_more'}
        </span>
      </button>

      {/* ── Dropdown ────────────────────────────────────────────── */}
      {isOpen && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={close} />

          <div className="absolute z-50 mt-1 w-full bg-white border border-slate-200 rounded-xl shadow-2xl overflow-hidden flex flex-col" style={{ maxHeight: '22rem' }}>
            {/* Search */}
            <div className="px-3 py-2 border-b border-slate-100 flex items-center gap-2 bg-slate-50/70">
              <span className="material-symbols-outlined text-sm text-slate-400">search</span>
              <input
                ref={inputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search models or providers..."
                className="flex-1 bg-transparent text-xs focus:outline-none text-slate-800 placeholder:text-slate-400"
              />
              {search && (
                <button onClick={() => setSearch('')} className="text-slate-400 hover:text-slate-600">
                  <span className="material-symbols-outlined text-sm">close</span>
                </button>
              )}
            </div>

            {/* List */}
            <div ref={listRef} className="overflow-y-auto flex-1">
              {Object.keys(filteredGroups).length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No models match &ldquo;{search}&rdquo;
                </div>
              ) : (
                Object.entries(filteredGroups).map(([pid, group]) => {
                  const header = (
                    <div
                      key={`h-${pid}`}
                      className="sticky top-0 z-10 bg-slate-50/90 backdrop-blur-sm px-3 py-1.5 flex items-center gap-2 border-b border-slate-100"
                    >
                      <img
                        src={group.logo_url}
                        alt=""
                        className="w-3.5 h-3.5"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                      />
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        {group.name}
                      </span>
                      <span className="text-[10px] text-slate-300 ml-auto">{group.models.length}</span>
                    </div>
                  );

                  const rows = group.models.map((model) => {
                    const idx = runIdx++;
                    const isSelected = model.id === value;
                    const isHighlighted = idx === highlightIdx;
                    const src = model.source || 'models.dev';

                    return (
                      <button
                        key={model.id}
                        type="button"
                        data-idx={idx}
                        onClick={() => { onChange(model.id); close(); }}
                        className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                          isHighlighted
                            ? 'bg-blue-50'
                            : isSelected
                            ? 'bg-blue-50/50'
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        {/* Model name */}
                        <span className={`font-mono truncate flex-1 ${isSelected ? 'text-blue-700 font-semibold' : 'text-slate-700'}`}>
                          {model.label || model.id}
                        </span>

                        {/* Source badge */}
                        <span className={`text-[8px] font-bold uppercase px-1 py-px rounded border flex-shrink-0 ${SOURCE_BADGE[src]?.cls || SOURCE_BADGE.custom.cls}`}>
                          {SOURCE_BADGE[src]?.label || src}
                        </span>

                        {/* Context window */}
                        {showContext && model.context_window && (
                          <span className="text-[10px] text-slate-400 flex-shrink-0 tabular-nums">{model.context_window}</span>
                        )}

                        {/* Tier */}
                        {showTier && model.tier && model.tier !== 'unknown' && (
                          <span className={`text-[8px] font-bold uppercase px-1 py-px rounded flex-shrink-0 ${TIER_COLORS[model.tier]}`}>
                            {model.tier}
                          </span>
                        )}

                        {/* Check */}
                        {isSelected && (
                          <span className="material-symbols-outlined text-blue-600 text-sm flex-shrink-0">check</span>
                        )}
                      </button>
                    );
                  });

                  return (
                    <div key={pid}>
                      {header}
                      {rows}
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer */}
            <div className="px-3 py-1.5 border-t border-slate-100 bg-slate-50/70 flex items-center justify-between text-[10px] text-slate-400">
              <span>{flatFiltered.length} model{flatFiltered.length !== 1 ? 's' : ''}</span>
              <span className="flex items-center gap-3">
                <span className="flex items-center gap-1">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${SOURCE_BADGE['models.dev'].cls.split(' ')[0]}`} />
                  catalog
                </span>
                <span className="flex items-center gap-1">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${SOURCE_BADGE.custom.cls.split(' ')[0]}`} />
                  custom
                </span>
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
