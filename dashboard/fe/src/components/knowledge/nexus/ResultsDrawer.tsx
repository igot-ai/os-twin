'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { QueryResultResponse, EntityHitResponse } from '@/hooks/use-knowledge-query';
import { getNodeColor } from '../constants';
import AnswerMarkdown from '../AnswerMarkdown';
import BacklinkBadge from '../BacklinkBadge';
import { FONT } from './typography';
import { Icon } from './Icon';

interface ResultsDrawerProps {
  result: QueryResultResponse | null;
  mode: string;
  isCollapsed: boolean;
  onToggle: () => void;
  onEntityClick: (entity: EntityHitResponse) => void;
  onNoteClick?: (noteId: string) => void;
  docked?: boolean;
}

export default function ResultsDrawer({
  result,
  mode,
  isCollapsed,
  onToggle,
  onEntityClick,
  onNoteClick,
  docked = false,
}: ResultsDrawerProps) {
  if (!result) return null;

  const hasWarning = result.warnings.includes('llm_unavailable');

  if (isCollapsed) {
    return (
      <button
        onClick={onToggle}
        className={docked ? `flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border ${FONT.body} font-medium transition-all hover:scale-[1.02]` : `absolute top-14 left-3 z-20 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border shadow-lg ${FONT.body} font-medium transition-all hover:scale-[1.02]`}
        style={{
          background: 'var(--surface-overlay-bg)',
          borderColor: 'var(--color-border)',
          backdropFilter: 'var(--surface-overlay-blur)',
        }}
      >
        <Icon name="description" size={14} style={{ color: 'var(--color-primary)' }} />
        {result.chunks.length} chunks · {result.entities.length} entities
      </button>
    );
  }

  return (
    <AnimatePresence>
      <motion.div
        key="results-drawer"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -20 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className={docked ? 'w-full max-h-full rounded-xl border flex flex-col overflow-hidden' : 'absolute top-14 left-3 z-20 w-[360px] max-h-[calc(100%-180px)] rounded-xl border shadow-2xl flex flex-col overflow-hidden'}
        style={{
          background: 'var(--surface-overlay-bg)',
          borderColor: 'var(--color-border)',
          backdropFilter: 'var(--surface-overlay-blur)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-3 py-2 border-b shrink-0"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <div className="flex items-center gap-2">
            <Icon name="description" size={16} style={{ color: 'var(--color-primary)' }} />
            <span className="text-xs font-semibold" style={{ color: 'var(--color-text-main)' }}>Results</span>
            <span
              className={`${FONT.caption} px-1.5 py-0.5 rounded-full`}
              style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
            >
              {result.chunks.length} chunks · {result.entities.length} entities
            </span>
          </div>
          <button onClick={onToggle} className="p-1 rounded-md hover:bg-white/10 transition-colors">
            <Icon name="chevron_left" size={14} style={{ color: 'var(--color-text-muted)' }} />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto p-3 space-y-3" style={{ scrollbarWidth: 'thin' }}>
          {hasWarning && mode === 'summarized' && (
            <div
              className={`p-2 rounded-lg ${FONT.body} flex items-start gap-2`}
              style={{ background: 'rgba(37, 99, 235, 0.08)', color: '#2563eb' }}
            >
              <Icon name="warning" size={16} />
              <span>LLM not configured. Showing graph results.</span>
            </div>
          )}

          {result.answer && (
            <div
              className="rounded-lg border p-3"
              style={{ background: 'var(--color-background)', borderColor: 'var(--color-border)' }}
            >
              <h5
                className={`${FONT.label} font-semibold uppercase tracking-wide mb-1.5 flex items-center gap-1`}
                style={{ color: 'var(--color-primary)' }}
              >
                <Icon name="auto_awesome" size={12} />
                Answer
              </h5>
              <AnswerMarkdown content={result.answer} />
            </div>
          )}

          {result.entities.length > 0 && (
            <div>
              <h5
                className={`${FONT.label} font-semibold uppercase tracking-wide mb-2`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                Click to locate on graph
              </h5>
              <div className="flex flex-wrap gap-1.5">
                {result.entities.map((entity, i) => {
                  const c = getNodeColor(entity.label);
                  return (
                    <button
                      key={i}
                      onClick={() => onEntityClick(entity)}
                      className={`px-2 py-1 rounded-md ${FONT.body} font-medium transition-all hover:scale-105 hover:shadow-md cursor-pointer`}
                      style={{
                        background: `${c}15`,
                        color: c,
                        border: `1px solid ${c}30`,
                      }}
                    >
                      <Icon name="my_location" size={11} className="align-middle mr-0.5" />
                      {entity.name}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {result.chunks.length > 0 && (
            <div>
              <h5
                className={`${FONT.label} font-semibold uppercase tracking-wide mb-2`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                Source Chunks
              </h5>
              <div className="space-y-2">
                {result.chunks.slice(0, 5).map((chunk, i) => (
                  <div
                    key={i}
                    className="rounded-lg border p-2.5"
                    style={{ background: 'var(--color-background)', borderColor: 'var(--color-border)' }}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className={`${FONT.label} font-medium truncate max-w-[200px]`} style={{ color: 'var(--color-text-muted)' }}>
                        {chunk.filename}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {chunk.memory_links && chunk.memory_links.length > 0 && (
                          <BacklinkBadge
                            memoryLinks={chunk.memory_links}
                            namespace={result.namespace}
                            onNoteClick={onNoteClick}
                          />
                        )}
                        <span
                          className={`px-1.5 py-0.5 rounded ${FONT.caption} font-bold`}
                          style={{ background: 'var(--color-primary-muted)', color: 'var(--color-primary)' }}
                        >
                          {chunk.score.toFixed(2)}
                        </span>
                      </div>
                    </div>
                    <p className={`${FONT.body} leading-relaxed`} style={{ color: 'var(--color-text-main)' }}>
                      {chunk.text.slice(0, 200)}{chunk.text.length > 200 ? '…' : ''}
                    </p>
                  </div>
                ))}
                {result.chunks.length > 5 && (
                  <p className={`${FONT.label} text-center`} style={{ color: 'var(--color-text-muted)' }}>
                    +{result.chunks.length - 5} more
                  </p>
                )}
              </div>
            </div>
          )}

          <div className={`${FONT.caption} text-right pt-1`} style={{ color: 'var(--color-text-faint)' }}>
            {result.latency_ms}ms
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
