'use client';

import { useState, useCallback, useRef } from 'react';
import { SearchResult } from '@/types';
import { apiFetch } from '@/lib/api';
import { trunc } from '@/lib/utils';

interface SearchBarProps {
  onSelectRoom: (roomId: string) => void;
}

export default function SearchBar({ onSelectRoom }: SearchBarProps) {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [showResults, setShowResults] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setShowResults(false);
      setResults([]);
      return;
    }

    try {
      const res = await apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`);
      if (!res.ok) {
        if (res.status === 503) {
          setResults([]);
          setShowResults(true);
        }
        return;
      }
      const data = await res.json();
      setResults(data.results || []);
      setShowResults(true);
    } catch (err) {
      console.error('Search failed:', err);
    }
  }, []);

  const handleInput = useCallback(
    (e: React.FormEvent<HTMLInputElement>) => {
      clearTimeout(timerRef.current);
      const value = (e.target as HTMLInputElement).value;
      timerRef.current = setTimeout(() => doSearch(value), 300);
    },
    [doSearch]
  );

  return (
    <div className="search-bar">
      <input
        type="text"
        className="search-input"
        placeholder="Search messages (semantic)…"
        onInput={handleInput}
        spellCheck={false}
      />
      {showResults && (
        <div className="search-results" style={{ display: 'block' }}>
          {results.length === 0 ? (
            <div className="search-result">
              <span style={{ color: 'var(--muted)' }}>No results</span>
            </div>
          ) : (
            results.map((r, i) => (
              <div
                key={i}
                className="search-result"
                onClick={() => {
                  onSelectRoom(r.room_id);
                  setShowResults(false);
                }}
              >
                <div className="search-result-header">
                  <span className="search-result-room">{r.room_id}</span>
                  <span className="search-result-type">{r.type}</span>
                  <span style={{ color: 'var(--muted)' }}>{r.ref}</span>
                  <span className="search-result-score">
                    {(r.score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="search-result-body">{trunc(r.body, 120)}</div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
