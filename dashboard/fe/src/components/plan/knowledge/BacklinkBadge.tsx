'use client';

import React, { useState } from 'react';

/**
 * Props for the BacklinkBadge component.
 */
interface BacklinkBadgeProps {
  /** Array of memory note IDs that link to this chunk */
  memoryLinks: string[];
  /** Callback when a note is clicked */
  onNoteClick?: (noteId: string) => void;
  /** Optional namespace for context */
  namespace?: string;
}

/**
 * A badge that shows the count of memory notes related to a knowledge chunk.
 * When clicked, expands to show a list of note IDs.
 * 
 * This is part of the Memory ↔ Knowledge Bridge (EPIC-007) that enables
 * bidirectional linking between memory notes and knowledge chunks.
 * 
 * @example
 * <BacklinkBadge
 *   memoryLinks={['note-uuid-1', 'note-uuid-2']}
 *   namespace="docs"
 *   onNoteClick={(id) => console.log('Navigate to', id)}
 * />
 */
export default function BacklinkBadge({
  memoryLinks,
  onNoteClick,
  namespace,
}: BacklinkBadgeProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Don't render if no links
  if (!memoryLinks || memoryLinks.length === 0) {
    return null;
  }

  const count = memoryLinks.length;

  return (
    <div className="relative">
      {/* Badge trigger */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-medium transition-all hover:scale-105"
        style={{
          background: 'var(--color-primary-muted)',
          color: 'var(--color-primary)',
          border: '1px solid var(--color-primary)',
        }}
        title={`${count} related note${count !== 1 ? 's' : ''}`}
      >
        <span className="material-symbols-outlined text-[12px]">link</span>
        <span>{count}</span>
      </button>

      {/* Expanded panel */}
      {isExpanded && (
        <div
          className="absolute top-full left-0 mt-1 z-50 min-w-[200px] max-w-[300px] rounded-lg border shadow-lg"
          style={{
            background: 'var(--color-surface)',
            borderColor: 'var(--color-border)',
          }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between px-3 py-2 border-b"
            style={{ borderColor: 'var(--color-border)' }}
          >
            <span
              className="text-[10px] font-semibold uppercase tracking-wide"
              style={{ color: 'var(--color-text-muted)' }}
            >
              📎 Related Notes
            </span>
            <button
              onClick={() => setIsExpanded(false)}
              className="p-0.5 rounded hover:bg-surface-hover transition-colors"
              aria-label="Close"
            >
              <span
                className="material-symbols-outlined text-[14px]"
                style={{ color: 'var(--color-text-muted)' }}
              >
                close
              </span>
            </button>
          </div>

          {/* Note list */}
          <div className="max-h-[200px] overflow-y-auto">
            {memoryLinks.map((noteId) => (
              <button
                key={noteId}
                onClick={() => {
                  onNoteClick?.(noteId);
                  setIsExpanded(false);
                }}
                className="w-full text-left px-3 py-2 text-xs hover:bg-surface-hover transition-colors flex items-center gap-2"
                style={{ color: 'var(--color-text-main)' }}
              >
                <span
                  className="material-symbols-outlined text-[14px]"
                  style={{ color: 'var(--color-primary)' }}
                >
                  description
                </span>
                <span className="truncate font-mono text-[10px]">
                  {noteId.length > 20 ? `${noteId.slice(0, 8)}...${noteId.slice(-4)}` : noteId}
                </span>
              </button>
            ))}
          </div>

          {/* Footer hint */}
          {namespace && (
            <div
              className="px-3 py-1.5 border-t text-[9px]"
              style={{
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-faint)',
              }}
            >
              Namespace: {namespace}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
