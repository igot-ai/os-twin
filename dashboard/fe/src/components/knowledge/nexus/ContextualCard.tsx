'use client';

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ExplorerNode, ExplorerEdge } from '@/hooks/use-knowledge-explorer';
import { getNodeColor } from '../constants';
import { useNexusContext } from './NexusContext';
import { FONT } from './typography';
import { Icon } from './Icon';

interface ContextualCardProps {
  node: ExplorerNode | null;
  edges: ExplorerEdge[];
  isLoading: boolean;
  onExpand: (nodeId: string) => Promise<void>;
  onTracePath: (sourceId: string) => void;
  onClose: () => void;
  docked?: boolean;
}

const SKIP_PROPERTY_KEYS = ['x', 'y', 'z', 'embedding', 'text'];

export default function ContextualCard({
  node,
  edges,
  isLoading,
  onExpand,
  onTracePath,
  onClose,
  docked = false,
}: ContextualCardProps) {
  const ctx = useNexusContext();
  const [showProperties, setShowProperties] = useState(false);
  const [textExpanded, setTextExpanded] = useState(false);
  const [selectedDepth, setSelectedDepth] = useState(1);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (node && cardRef.current) {
      cardRef.current.focus();
    }
  }, [node]);

  const connectedEdges = useMemo(() => {
    if (!node) return [];
    return edges.filter(e => {
      const sourceId = typeof e.source === 'string' ? e.source : (e.source as any).id;
      const targetId = typeof e.target === 'string' ? e.target : (e.target as any).id;
      return sourceId === node.id || targetId === node.id;
    });
  }, [node, edges]);

  const neighborCount = connectedEdges.length;

  const edgesByLabel = useMemo(() => {
    if (!node) return new Map();
    const map = new Map<string, { in: ExplorerNode[], out: ExplorerNode[] }>();
    const nodeMap = new Map(ctx.graph.nodes.map(n => [n.id, n]));

    for (const e of connectedEdges) {
      const sourceId = typeof e.source === 'string' ? e.source : (e.source as any).id;
      const targetId = typeof e.target === 'string' ? e.target : (e.target as any).id;
      const label = e.label || 'Unknown';
      
      if (!map.has(label)) map.set(label, { in: [], out: [] });

      if (sourceId === node.id) {
        const targetNode = nodeMap.get(targetId);
        if (targetNode) map.get(label)!.out.push(targetNode);
      } else {
        const sourceNode = nodeMap.get(sourceId);
        if (sourceNode) map.get(label)!.in.push(sourceNode);
      }
    }
    return map;
  }, [node, connectedEdges, ctx.graph.nodes]);

  const [expandedRelationships, setExpandedRelationships] = useState<Set<string>>(new Set());
  const toggleRelationship = (label: string) => {
    setExpandedRelationships(prev => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  };

  const prologue = (() => {
    if (!node) return null;
    for (const entry of ctx.trail.trail) {
      if (entry.action.type === 'seed') {
        return { source: 'seed', label: `seed(${entry.action.topK})` };
      }
      if (entry.action.type === 'expand' && entry.action.nodeId === node.id) {
        return { source: 'expand', label: `expanded from ${node.id.slice(0, 8)}` };
      }
    }
    return null;
  })();

  if (!node) return null;

  const color = getNodeColor(node.label);
  const propertyKeys = node.properties ? Object.keys(node.properties) : [];
  const textContent = node.label === 'text_chunk' && node.properties?.text
    ? node.properties.text as string
    : null;
  const filteredPropertyKeys = propertyKeys.filter(k => !SKIP_PROPERTY_KEYS.includes(k));

  const renderValue = (val: unknown): string => {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'string') return val.length > 120 ? val.slice(0, 120) + '…' : val;
    if (typeof val === 'number' || typeof val === 'boolean') return String(val);
    return JSON.stringify(val);
  };

  const isUrlLike = (val: unknown): val is string =>
    typeof val === 'string' && (val.startsWith('http://') || val.startsWith('https://'));

  const handleExpand = () => {
    onExpand(node.id);
  };

  return (
    <AnimatePresence>
      <motion.div
        key={node.id}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className={docked ? 'w-full rounded-xl border shadow-2xl overflow-hidden outline-none' : 'absolute top-14 right-3 z-20 w-[360px] rounded-xl border shadow-2xl overflow-hidden outline-none'}
        ref={cardRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={`${node.label} details`}
        style={{
          background: 'var(--surface-overlay-bg)',
          borderColor: `${color}30`,
          backdropFilter: 'var(--surface-overlay-blur)',
        }}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-3 pt-3 pb-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
            <span
              className={`${FONT.caption} uppercase tracking-wide font-semibold`}
              style={{ color }}
            >
              {node.label}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-white/10 transition-colors shrink-0"
          >
            <Icon name="close" size={14} style={{ color: 'var(--color-text-muted)' }} />
          </button>
        </div>

        {/* Name */}
        <div className="px-3 pb-2">
          <h4 className="text-sm font-semibold leading-tight" style={{ color: 'var(--color-text-main)' }}>
            {node.name}
          </h4>
        </div>

        {/* Prologue / backlinks */}
        {prologue && (
          <div className="px-3 pb-2">
            <span
              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded ${FONT.caption}`}
              style={{
                background: 'rgba(100, 116, 139, 0.1)',
                color: 'var(--color-text-muted)',
              }}
            >
              <Icon name={prologue.source === 'seed' ? 'explore' : 'bubble'} size={10} />
              {prologue.label}
            </span>
          </div>
        )}

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

        {/* text_chunk content — special rendering */}
        {textContent && (
          <div className="px-3 pb-2">
            <div
              className={`rounded-lg border p-2.5 ${FONT.body} leading-relaxed`}
              style={{
                background: 'var(--color-background)',
                borderColor: 'var(--color-border)',
                color: 'var(--color-text-main)',
                maxHeight: textExpanded ? '320px' : '120px',
                overflow: 'hidden',
                transition: 'max-height 0.2s ease',
              }}
            >
              {textExpanded ? textContent : textContent.slice(0, 500)}
              {!textExpanded && textContent.length > 500 && '…'}
            </div>
            {textContent.length > 500 && (
              <button
                onClick={() => setTextExpanded(!textExpanded)}
                className={`mt-1 ${FONT.label} font-medium`}
                style={{ color: 'var(--color-primary)' }}
              >
                {textExpanded ? 'Show less' : `Show more (${textContent.length} chars)`}
              </button>
            )}
          </div>
        )}

        {/* Properties */}
        {filteredPropertyKeys.length > 0 && (
          <div className="px-3 pb-2 border-b border-white/5 mb-2">
            <button
              onClick={() => setShowProperties(!showProperties)}
              className={`flex items-center gap-1 ${FONT.label} font-medium cursor-pointer mb-2`}
              style={{ color: 'var(--color-text-muted)' }}
            >
              <Icon name={showProperties ? 'expand_less' : 'expand_more'} size={12} />
              Properties ({filteredPropertyKeys.length})
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
                  <div className="space-y-0.5 max-h-[320px] overflow-y-auto pb-2">
                    {filteredPropertyKeys.map(key => {
                      const val = (node.properties as Record<string, unknown>)?.[key];
                      return (
                        <div key={key} className={`flex gap-2 ${FONT.caption}`}>
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

        {/* Semantic Inspector: Relationships Grouped by Edge Label */}
        {edgesByLabel.size > 0 && (
          <div className="px-3 pb-2 flex-1 overflow-y-auto custom-scrollbar">
            <div className={`mb-2 font-semibold ${FONT.caption} uppercase tracking-wider text-[var(--color-text-muted)]`}>
              Relationships
            </div>
            <div className="space-y-1">
              {Array.from(edgesByLabel.entries()).map(([edgeLabel, group]) => {
                const isExpanded = expandedRelationships.has(edgeLabel);
                const totalEntities = group.in.length + group.out.length;
                return (
                  <div key={edgeLabel} className="rounded-lg bg-black/10 border border-white/5 overflow-hidden">
                    <button
                      onClick={() => {
                         toggleRelationship(edgeLabel);
                         // Auto highlight the edge label on the graph when exploring it
                         if (!isExpanded) {
                           ctx.graph.setHighlightedEdges(new Set([edgeLabel]));
                         } else {
                           ctx.graph.setHighlightedEdges(new Set());
                         }
                      }}
                      className="w-full flex items-center justify-between px-2 py-1.5 hover:bg-white/5 transition-colors"
                    >
                      <div className="flex items-center gap-1.5">
                        <Icon name={isExpanded ? 'expand_more' : 'chevron_right'} size={14} style={{ color: 'var(--color-text-muted)' }} />
                        <span className={`font-medium ${FONT.caption}`} style={{ color: 'var(--color-text-main)' }}>{edgeLabel}</span>
                      </div>
                      <span className={`px-1.5 py-0.5 rounded bg-white/10 ${FONT.caption}`} style={{ fontSize: 10, color: 'var(--color-text-muted)' }}>
                        {totalEntities}
                      </span>
                    </button>
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden bg-black/20"
                        >
                          <div className="px-2 py-1.5 space-y-1 max-h-48 overflow-y-auto custom-scrollbar">
                            {group.out.length > 0 && (
                              <div className="mb-1.5">
                                <div className={`text-[9px] uppercase font-bold text-[var(--color-text-faint)] mb-1 pl-1`}>Outgoing ({group.out.length})</div>
                                {group.out.map((targetNode: ExplorerNode) => (
                                  <div 
                                    key={targetNode.id} 
                                    onClick={() => ctx.actions.selectNode(targetNode)}
                                    className={`flex items-center gap-1.5 px-1.5 py-1 rounded cursor-pointer hover:bg-white/10 transition-colors ${FONT.caption}`}
                                  >
                                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: getNodeColor(targetNode.label) }} />
                                    <span className="truncate" style={{ color: 'var(--color-text-main)' }} title={targetNode.name}>{targetNode.name}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            {group.in.length > 0 && (
                              <div>
                                <div className={`text-[9px] uppercase font-bold text-[var(--color-text-faint)] mb-1 pl-1`}>Incoming ({group.in.length})</div>
                                {group.in.map((sourceNode: ExplorerNode) => (
                                  <div 
                                    key={sourceNode.id} 
                                    onClick={() => ctx.actions.selectNode(sourceNode)}
                                    className={`flex items-center gap-1.5 px-1.5 py-1 rounded cursor-pointer hover:bg-white/10 transition-colors ${FONT.caption}`}
                                  >
                                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: getNodeColor(sourceNode.label) }} />
                                    <span className="truncate" style={{ color: 'var(--color-text-main)' }} title={sourceNode.name}>{sourceNode.name}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Actions with depth selector */}
        <div
          className="px-3 py-2 border-t flex gap-2"
          style={{ borderColor: 'var(--color-border)' }}
        >
          <div className="flex-1 flex items-center gap-1">
            <button
              onClick={handleExpand}
              disabled={isLoading}
              className={`flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg ${FONT.body} font-medium border transition-colors hover:bg-white/5 disabled:opacity-50`}
              style={{ borderColor: `${color}40`, color }}
            >
              <Icon name="bubble" size={14} />
              Expand
            </button>
            <div className="flex items-center gap-0.5">
              {[1, 2, 3].map(d => (
                <button
                  key={d}
                  onClick={() => {
                    setSelectedDepth(d);
                    ctx.actions.setDepth(d);
                  }}
                  className={`w-5 h-5 rounded ${FONT.caption} font-medium border transition-colors`}
                  style={{
                    borderColor: selectedDepth === d ? color : 'var(--color-border)',
                    color: selectedDepth === d ? color : 'var(--color-text-muted)',
                    background: selectedDepth === d ? `${color}15` : 'transparent',
                  }}
                >
                  d{d}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() => onTracePath(node.id)}
            className={`flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg ${FONT.body} font-medium border transition-colors hover:bg-white/5`}
            style={{ borderColor: 'rgba(251, 191, 36, 0.3)', color: '#fbbf24' }}
          >
            <Icon name="route" size={14} />
            Path
          </button>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
