'use client';

import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ExplorerNode, ExplorerEdge } from '@/hooks/use-knowledge-explorer';
import { getNodeColor } from '../constants';

interface ContextualCardProps {
  node: ExplorerNode | null;
  edges: ExplorerEdge[];
  isLoading: boolean;
  onExpand: (nodeId: string) => Promise<void>;
  onTracePath: (sourceId: string) => void;
  onClose: () => void;
}

export default function ContextualCard({
  node,
  edges,
  isLoading,
  onExpand,
  onTracePath,
  onClose,
}: ContextualCardProps) {
  const [showProperties, setShowProperties] = useState(false);

  const neighborCount = useMemo(() => {
    if (!node) return 0;
    let count = 0;
    for (const edge of edges) {
      if (edge.source === node.id || edge.target === node.id) count++;
    }
    return count;
  }, [node, edges]);

  if (!node) return null;

  const color = getNodeColor(node.label);
  const propertyKeys = node.properties ? Object.keys(node.properties) : [];

  const renderValue = (val: unknown): string => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'string') return val.length > 120 ? val.slice(0, 120) + '…' : val;
    if (typeof val === 'number' || typeof val === 'boolean') return String(val);
    return JSON.stringify(val);
  };

  const isUrlLike = (val: unknown): val is string =>
    typeof val === 'string' && (val.startsWith('http://') || val.startsWith('https://'));

  return (
    <AnimatePresence>
      <motion.div
        key={node.id}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className="absolute top-14 right-3 z-20 w-[360px] rounded-xl border shadow-2xl overflow-hidden"
        style={{
          background: 'rgba(255, 255, 255, 0.95)',
          borderColor: `${color}30`,
          backdropFilter: 'blur(16px)',
        }}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-3 pt-3 pb-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
            <span
              className="text-[9px] uppercase tracking-wide font-semibold"
              style={{ color }}
            >
              {node.label}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-white/10 transition-colors shrink-0"
          >
            <span className="material-symbols-outlined text-[14px]" style={{ color: 'var(--color-text-muted)' }}>close</span>
          </button>
        </div>

        {/* Name */}
        <div className="px-3 pb-2">
          <h4 className="text-sm font-semibold leading-tight" style={{ color: 'var(--color-text-main)' }}>
            {node.name}
          </h4>
        </div>

        {/* Stats */}
        <div className="px-3 pb-2 space-y-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
          <div className="flex justify-between">
            <span>Score</span>
            <span className="font-medium" style={{ color: 'var(--color-text-main)' }}>{node.score.toFixed(2)}</span>
          </div>
          {node.degree !== undefined && (
            <div className="flex justify-between">
              <span>Degree</span>
              <span className="font-medium" style={{ color: 'var(--color-text-main)' }}>{node.degree}</span>
            </div>
          )}
          {neighborCount > 0 && (
            <div className="flex justify-between">
              <span>Neighbors</span>
              <span className="font-medium" style={{ color: 'var(--color-text-main)' }}>{neighborCount}</span>
            </div>
          )}
        </div>

        {/* Properties */}
        {propertyKeys.length > 0 && (
          <div className="px-3 pb-2">
            <button
              onClick={() => setShowProperties(!showProperties)}
              className="flex items-center gap-1 text-[10px] font-medium cursor-pointer"
              style={{ color: 'var(--color-text-muted)' }}
            >
              <span className="material-symbols-outlined text-[12px]">
                {showProperties ? 'expand_less' : 'expand_more'}
              </span>
              Properties ({propertyKeys.length})
            </button>
            <AnimatePresence>
              {showProperties && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.15 }}
                  className="overflow-hidden"
                >
                  <div className="mt-1 space-y-0.5 max-h-[160px] overflow-y-auto">
                    {propertyKeys.map(key => {
                      const val = (node.properties as Record<string, unknown>)?.[key];
                      const skip = ['x', 'y', 'z', 'embedding'];
                      if (skip.includes(key)) return null;
                      return (
                        <div key={key} className="flex gap-2 text-[9px]">
                          <span className="shrink-0 font-medium min-w-[60px] text-right" style={{ color: 'var(--color-text-muted)' }}>
                            {key}
                          </span>
                          {isUrlLike(val) ? (
                            <a href={val} target="_blank" rel="noopener noreferrer" className="truncate underline" style={{ color: 'var(--color-primary)' }}>
                              {val.replace(/^https?:\/\//, '')}
                            </a>
                          ) : (
                            <span className="truncate" style={{ color: 'var(--color-text-main)' }}>
                              {renderValue(val)}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Actions */}
        <div
          className="px-3 py-2 border-t flex gap-2"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <button
            onClick={() => onExpand(node.id)}
            disabled={isLoading}
            className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-white/5 disabled:opacity-50"
            style={{ borderColor: `${color}40`, color }}
          >
            <span className="material-symbols-outlined text-[14px]">bubble</span>
            Expand
          </button>
          <button
            onClick={() => onTracePath(node.id)}
            className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-white/5"
            style={{ borderColor: 'rgba(251, 191, 36, 0.3)', color: '#fbbf24' }}
          >
            <span className="material-symbols-outlined text-[14px]">route</span>
            Path
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
