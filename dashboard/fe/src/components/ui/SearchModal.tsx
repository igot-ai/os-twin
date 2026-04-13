'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Modal } from './Modal';
import { useUIStore } from '@/lib/stores/uiStore';
import { apiGet } from '@/lib/api-client';
import type { Skill, Plan } from '@/types';

interface SearchResult {
  id: string;
  type: 'skill' | 'plan';
  title: string;
  description?: string;
  meta?: string;
  href: string;
}

export const SearchModal = () => {
  const router = useRouter();
  const { searchModalOpen, setSearchModalOpen } = useUIStore();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!searchModalOpen) {
      setQuery('');
      setResults([]);
      setSelectedIndex(0);
    }
  }, [searchModalOpen]);

  const performSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const [skills, plans] = await Promise.allSettled([
        apiGet<Skill[]>(`/skills/search?q=${encodeURIComponent(q)}`),
        apiGet<Plan[]>('/plans'),
      ]);

      const combined: SearchResult[] = [];

      // Add skill results
      if (skills.status === 'fulfilled' && Array.isArray(skills.value)) {
        for (const skill of skills.value.slice(0, 8)) {
          combined.push({
            id: `skill-${skill.name}`,
            type: 'skill',
            title: skill.name,
            description: skill.description,
            meta: skill.category,
            href: '/skills',
          });
        }
      }

      // Filter and add plan results (client-side text match)
      if (plans.status === 'fulfilled' && Array.isArray(plans.value)) {
        const lq = q.toLowerCase();
        const matched = plans.value.filter(
          (p) =>
            p.title?.toLowerCase().includes(lq) ||
            p.goal?.toLowerCase().includes(lq) ||
            p.plan_id?.toLowerCase().includes(lq),
        );
        for (const plan of matched.slice(0, 8)) {
          combined.push({
            id: `plan-${plan.plan_id}`,
            type: 'plan',
            title: plan.title,
            description: plan.goal,
            meta: plan.status,
            href: `/plans/${plan.plan_id}`,
          });
        }
      }

      setResults(combined);
      setSelectedIndex(0);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  // Debounced search
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!query.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    debounceRef.current = setTimeout(() => performSearch(query), 250);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, performSearch]);

  // Navigate to selected result
  const handleSelect = useCallback(
    (result: SearchResult) => {
      setSearchModalOpen(false);
      router.push(result.href);
    },
    [router, setSearchModalOpen],
  );

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && results[selectedIndex]) {
        e.preventDefault();
        handleSelect(results[selectedIndex]);
      }
    },
    [results, selectedIndex, handleSelect],
  );

  // Scroll selected item into view
  useEffect(() => {
    const el = listRef.current?.children[selectedIndex] as HTMLElement | undefined;
    el?.scrollIntoView({ block: 'nearest' });
  }, [selectedIndex]);

  // Group results by type
  const skillResults = results.filter((r) => r.type === 'skill');
  const planResults = results.filter((r) => r.type === 'plan');

  return (
    <Modal
      isOpen={searchModalOpen}
      onClose={() => setSearchModalOpen(false)}
      title="Search"
      size="lg"
    >
      <div className="space-y-2" onKeyDown={handleKeyDown}>
        <div className="relative">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-text-faint">
            search
          </span>
          <input
            autoFocus
            type="text"
            placeholder="Search skills, plans..."
            className="w-full pl-10 pr-4 py-3 bg-background border border-border rounded-xl focus:outline-none focus:ring-2 focus:ring-primary text-text-main"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            role="searchbox"
            aria-label="Search input"
          />
        </div>

        {/* Results */}
        <div
          ref={listRef}
          className="max-h-[50vh] overflow-y-auto"
          role="listbox"
        >
          {loading && query.trim() && (
            <div className="flex items-center justify-center py-8">
              <span className="material-symbols-outlined text-xl text-text-faint animate-spin">
                progress_activity
              </span>
            </div>
          )}

          {!loading && query.trim() && results.length === 0 && (
            <div className="py-8 text-center">
              <span className="material-symbols-outlined text-3xl text-text-faint block mb-2">
                search_off
              </span>
              <p className="text-sm text-text-muted">
                No results for &ldquo;{query}&rdquo;
              </p>
            </div>
          )}

          {!loading && results.length > 0 && (
            <div className="space-y-3 py-2">
              {/* Skills section */}
              {skillResults.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 px-3 py-1.5">
                    <span className="material-symbols-outlined text-xs text-text-faint">auto_awesome</span>
                    <span className="text-[10px] font-bold uppercase tracking-widest text-text-faint">
                      Skills
                    </span>
                    <span className="text-[10px] text-text-faint">{skillResults.length}</span>
                  </div>
                  {skillResults.map((r) => {
                    const globalIdx = results.indexOf(r);
                    return (
                      <button
                        key={r.id}
                        type="button"
                        role="option"
                        aria-selected={globalIdx === selectedIndex}
                        onClick={() => handleSelect(r)}
                        className={`w-full text-left px-3 py-2.5 rounded-lg flex items-start gap-3 transition-colors cursor-pointer ${
                          globalIdx === selectedIndex
                            ? 'bg-primary/10 border border-primary/20'
                            : 'hover:bg-surface-hover'
                        }`}
                      >
                        <span className="material-symbols-outlined text-sm mt-0.5 text-primary flex-shrink-0">
                          auto_awesome
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-text-main truncate">
                            {r.title}
                          </div>
                          {r.description && (
                            <div className="text-xs text-text-muted line-clamp-1 mt-0.5">
                              {r.description}
                            </div>
                          )}
                        </div>
                        {r.meta && (
                          <span className="text-[10px] font-medium text-text-faint bg-surface-hover px-1.5 py-0.5 rounded flex-shrink-0">
                            {r.meta}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* Plans section */}
              {planResults.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 px-3 py-1.5">
                    <span className="material-symbols-outlined text-xs text-text-faint">description</span>
                    <span className="text-[10px] font-bold uppercase tracking-widest text-text-faint">
                      Plans
                    </span>
                    <span className="text-[10px] text-text-faint">{planResults.length}</span>
                  </div>
                  {planResults.map((r) => {
                    const globalIdx = results.indexOf(r);
                    return (
                      <button
                        key={r.id}
                        type="button"
                        role="option"
                        aria-selected={globalIdx === selectedIndex}
                        onClick={() => handleSelect(r)}
                        className={`w-full text-left px-3 py-2.5 rounded-lg flex items-start gap-3 transition-colors cursor-pointer ${
                          globalIdx === selectedIndex
                            ? 'bg-primary/10 border border-primary/20'
                            : 'hover:bg-surface-hover'
                        }`}
                      >
                        <span className="material-symbols-outlined text-sm mt-0.5 text-blue-600 flex-shrink-0">
                          description
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-semibold text-text-main truncate">
                            {r.title}
                          </div>
                          {r.description && (
                            <div className="text-xs text-text-muted line-clamp-1 mt-0.5">
                              {r.description}
                            </div>
                          )}
                        </div>
                        {r.meta && (
                          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded flex-shrink-0 ${
                            r.meta === 'active'
                              ? 'text-green-700 bg-green-100'
                              : r.meta === 'completed'
                                ? 'text-blue-700 bg-blue-100'
                                : 'text-text-faint bg-surface-hover'
                          }`}>
                            {r.meta}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Empty state when no query */}
          {!query.trim() && (
            <div className="py-8 text-center">
              <div className="w-16 h-16 bg-surface-hover rounded-2xl flex items-center justify-center mx-auto mb-4">
                <span className="material-symbols-outlined text-3xl text-text-faint">
                  manage_search
                </span>
              </div>
              <p className="text-sm font-bold text-text-main">Search Skills & Plans</p>
              <p className="text-xs text-text-muted max-w-[280px] mx-auto mt-1">
                Find skills by name or description, and plans by title or goal.
              </p>
            </div>
          )}
        </div>

        <div className="pt-3 border-t border-border flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
              <kbd className="px-1 py-0.5 rounded border border-border bg-background shadow-sm font-mono">
                &uarr;&darr;
              </kbd>
              <span>to navigate</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
              <kbd className="px-1 py-0.5 rounded border border-border bg-background shadow-sm font-mono">
                &crarr;
              </kbd>
              <span>to select</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-[10px] text-text-faint">
            <kbd className="px-1 py-0.5 rounded border border-border bg-background shadow-sm font-mono">
              esc
            </kbd>
            <span>to close</span>
          </div>
        </div>
      </div>
    </Modal>
  );
};
