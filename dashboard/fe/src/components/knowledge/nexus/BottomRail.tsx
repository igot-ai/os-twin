'use client';

import React, { useMemo, useState, useRef, useEffect } from 'react';
import { useNexusContext } from './NexusContext';
import { getNodeColor, EDGE_LABEL_COLORS } from '../constants';
import { FONT } from './typography';
import { Icon } from './Icon';

export default function BottomRail() {
  const ctx = useNexusContext();
  const { graph, actions } = ctx;

  const [showNodeMenu, setShowNodeMenu] = useState(false);
  const [showEdgeMenu, setShowEdgeMenu] = useState(false);
  const nodeMenuRef = useRef<HTMLDivElement>(null);
  const edgeMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (edgeMenuRef.current && !edgeMenuRef.current.contains(e.target as Node)) {
        setShowEdgeMenu(false);
      }
      if (nodeMenuRef.current && !nodeMenuRef.current.contains(e.target as Node)) {
        setShowNodeMenu(false);
      }
    };
    if (showEdgeMenu || showNodeMenu) {
      document.addEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showEdgeMenu, showNodeMenu]);

  const labelCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of graph.nodes) counts.set(n.label, (counts.get(n.label) ?? 0) + 1);
    return counts;
  }, [graph.nodes]);

  const labels = useMemo(() => {
    return Array.from(labelCounts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([label]) => label);
  }, [labelCounts]);

  const edgeLabels = useMemo(() => {
    const counts = new Map<string, number>();

    let activeNodes: Set<string> | null = null;
    if (graph.highlightedLabels.size > 0) {
      activeNodes = new Set(
        graph.nodes
          .filter(n => graph.highlightedLabels.has(n.label))
          .map(n => n.id)
      );
    }

    for (const e of graph.edges) {
      if (e.label && e.label !== 'RELATES') {
        if (activeNodes) {
          const sourceId = typeof e.source === 'string' ? e.source : (e.source as any).id;
          const targetId = typeof e.target === 'string' ? e.target : (e.target as any).id;
          if (!activeNodes.has(sourceId) && !activeNodes.has(targetId)) {
            continue;
          }
        }
        counts.set(e.label, (counts.get(e.label) ?? 0) + 1);
      }
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([label]) => label);
  }, [graph.edges, graph.nodes, graph.highlightedLabels]);

  return (
    <div
      className="col-span-3 flex items-center gap-3 px-3 border-t shrink-0 overflow-visible relative"
      style={{
        height: 36,
        background: 'var(--surface-overlay-bg)',
        borderColor: 'var(--color-border)',
        backdropFilter: 'var(--surface-overlay-blur)',
      }}
    >
      {/* Left: node type filters (Entities dropdown) */}
      {labels.length > 0 && (
        <div className="relative shrink-0" ref={nodeMenuRef}>
          <button
            onClick={() => {
              setShowNodeMenu(!showNodeMenu);
              setShowEdgeMenu(false); // close the other menu
            }}
            className={`flex items-center gap-1.5 px-2 py-1 rounded border transition-colors ${FONT.caption}`}
            style={{
              borderColor: 'var(--color-border)',
              background: showNodeMenu ? 'var(--color-surface-hover)' : 'transparent',
              color: 'var(--color-text-main)'
            }}
          >
            <Icon name="category" size={14} />
            Entities {graph.highlightedLabels.size > 0 ? `(${graph.highlightedLabels.size})` : ''}
            <Icon name={showNodeMenu ? 'expand_less' : 'expand_more'} size={14} />
          </button>
          
          {showNodeMenu && (
            <div 
              className="absolute bottom-[calc(100%+8px)] left-0 w-64 max-h-64 overflow-y-auto rounded-lg border shadow-xl flex flex-col p-1 z-50 custom-scrollbar"
              style={{
                background: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
              }}
            >
              <div className="px-2 py-1.5 border-b mb-1 flex items-center justify-between sticky top-0 bg-[var(--color-surface)] z-10" style={{ borderColor: 'var(--color-border)' }}>
                <span className={`font-semibold text-[var(--color-text-main)] ${FONT.caption}`}>Filter Entities</span>
                {graph.highlightedLabels.size > 0 && (
                  <button 
                    onClick={(e) => { e.stopPropagation(); graph.setHighlightedLabels(new Set()); }}
                    className={`text-[var(--color-primary)] hover:underline ${FONT.caption}`}
                  >
                    Clear
                  </button>
                )}
              </div>
              {labels.map(label => {
                const color = getNodeColor(label);
                const count = labelCounts.get(label) ?? 0;
                const isSelected = graph.highlightedLabels.has(label);
                return (
                  <label
                    key={label}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors hover:bg-[var(--color-surface-hover)] ${FONT.caption}`}
                  >
                    <input 
                      type="checkbox" 
                      checked={isSelected}
                      onChange={() => {
                        graph.setHighlightedLabels(prev => {
                          const next = new Set(prev);
                          if (next.has(label)) next.delete(label);
                          else next.add(label);
                          return next;
                        });
                      }}
                      className="rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
                    />
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                    <span className="truncate flex-1" style={{ color: 'var(--color-text-main)' }} title={label}>{label}</span>
                    <span className="opacity-60 text-[10px]">·{count}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Center: edge legend multi-select list */}
      {edgeLabels.length > 0 && (
        <div className="relative shrink-0" ref={edgeMenuRef}>
          <button
            onClick={() => {
              setShowEdgeMenu(!showEdgeMenu);
              setShowNodeMenu(false); // close the other menu
            }}
            className={`flex items-center gap-1.5 px-2 py-1 rounded border transition-colors ${FONT.caption}`}
            style={{
              borderColor: 'var(--color-border)',
              background: showEdgeMenu ? 'var(--color-surface-hover)' : 'transparent',
              color: 'var(--color-text-main)'
            }}
          >
            <Icon name="share" size={14} />
            Relationships {graph.highlightedEdges.size > 0 ? `(${graph.highlightedEdges.size})` : ''}
            <Icon name={showEdgeMenu ? 'expand_less' : 'expand_more'} size={14} />
          </button>
          
          {showEdgeMenu && (
            <div 
              className="absolute bottom-[calc(100%+8px)] right-0 w-64 max-h-64 overflow-y-auto rounded-lg border shadow-xl flex flex-col p-1 z-50 custom-scrollbar"
              style={{
                background: 'var(--color-surface)',
                borderColor: 'var(--color-border)',
              }}
            >
              <div className="px-2 py-1.5 border-b mb-1 flex items-center justify-between sticky top-0 bg-[var(--color-surface)] z-10" style={{ borderColor: 'var(--color-border)' }}>
                <span className={`font-semibold text-[var(--color-text-main)] ${FONT.caption}`}>Filter Relationships</span>
                {graph.highlightedEdges.size > 0 && (
                  <button 
                    onClick={(e) => { e.stopPropagation(); graph.setHighlightedEdges(new Set()); }}
                    className={`text-[var(--color-primary)] hover:underline ${FONT.caption}`}
                  >
                    Clear
                  </button>
                )}
              </div>
              {edgeLabels.map(label => {
                const c = EDGE_LABEL_COLORS[label.toUpperCase()] ?? '#6b7280';
                const isSelected = graph.highlightedEdges.has(label);
                return (
                  <label
                    key={label}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors hover:bg-[var(--color-surface-hover)] ${FONT.caption}`}
                  >
                    <input 
                      type="checkbox" 
                      checked={isSelected}
                      onChange={() => {
                        graph.setHighlightedEdges(prev => {
                          const next = new Set(prev);
                          if (next.has(label)) next.delete(label);
                          else next.add(label);
                          return next;
                        });
                      }}
                      className="rounded border-[var(--color-border)] text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
                    />
                    <span className="w-3 h-0.5 shrink-0" style={{ background: c }} />
                    <span style={{ color: 'var(--color-text-main)' }}>{label}</span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Right: stats + actions */}
      <div className="flex items-center gap-2 shrink-0 ml-auto">
        {!graph.isSeeded ? (
          <button
            onClick={() => actions.seed(50)}
            disabled={graph.isLoading}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg ${FONT.body} font-semibold text-white transition-all disabled:opacity-50`}
            style={{ background: 'var(--color-primary)' }}
          >
            <Icon name={graph.isLoading ? 'progress_activity' : 'explore'} size={16} />
            {graph.isLoading ? 'Loading...' : 'Sonar Ping'}
          </button>
        ) : (
          <>
            <button
              onClick={actions.reset}
              className={`flex items-center gap-1 px-2 py-1 rounded-lg ${FONT.label} font-medium border transition-colors hover:bg-white/5`}
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
            >
              <Icon name="restart_alt" size={12} />
              Reset
            </button>
          </>
        )}
        <div className={`flex items-center gap-3 ${FONT.caption}`} style={{ color: 'var(--color-text-muted)' }}>
          {graph.isSeeded && graph.nodes.length > 0 && (
            <>
              <span>{graph.nodes.length} nodes</span>
              <span>{graph.edges.length} edges</span>
              {graph.activeIgnitionPoints.length > 0 && (
                <span style={{ color: 'var(--color-primary)' }}>{graph.activeIgnitionPoints.length} ignited</span>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
