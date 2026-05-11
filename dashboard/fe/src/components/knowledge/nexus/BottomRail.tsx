'use client';

import React, { useMemo } from 'react';
import { useNexusContext } from './NexusContext';
import { getNodeColor, EDGE_LABEL_COLORS } from '../constants';
import { FONT } from './typography';
import { Icon } from './Icon';

export default function BottomRail() {
  const ctx = useNexusContext();
  const { graph, actions } = ctx;

  const labelCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const n of graph.nodes) counts.set(n.label, (counts.get(n.label) ?? 0) + 1);
    return counts;
  }, [graph.nodes]);

  const labels = useMemo(() => {
    const set = new Set(graph.nodes.map(n => n.label));
    return Array.from(set).sort();
  }, [graph.nodes]);

  const edgeLabels = useMemo(() => {
    const set = new Set(
      graph.edges
        .map(e => e.label)
        .filter(l => l && l !== 'RELATES'),
    );
    return Array.from(set).sort();
  }, [graph.edges]);

  return (
    <div
      className="col-span-3 flex items-center gap-3 px-3 border-t shrink-0 overflow-hidden"
      style={{
        height: 36,
        background: 'var(--surface-overlay-bg)',
        borderColor: 'var(--color-border)',
        backdropFilter: 'var(--surface-overlay-blur)',
      }}
    >
      {/* Left: node type filters */}
      {labels.length > 1 && (
        <div className="flex items-center gap-1 overflow-hidden min-w-0 flex-1">
          {labels.slice(0, 12).map(label => {
            const isHighlighted = graph.highlightedLabels.has(label);
            const color = getNodeColor(label);
            const count = labelCounts.get(label) ?? 0;
            return (
              <button
                key={label}
                onClick={() => {
                  graph.setHighlightedLabels(prev => {
                    const next = new Set(prev);
                    if (next.has(label)) next.delete(label);
                    else next.add(label);
                    return next;
                  });
                }}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded ${FONT.caption} border transition-all cursor-pointer shrink-0`}
                style={{
                  color: isHighlighted ? color : `${color}80`,
                  borderColor: isHighlighted ? color : `${color}30`,
                  background: isHighlighted ? `${color}18` : `${color}08`,
                  fontWeight: isHighlighted ? 600 : 400,
                }}
              >
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: color, opacity: isHighlighted ? 1 : 0.5 }} />
                {label}
                <span className="opacity-60">·{count}</span>
              </button>
            );
          })}
          {labels.length > 12 && (
            <span className={`${FONT.caption} px-1 shrink-0`} style={{ color: 'var(--color-text-faint)' }}>
              +{labels.length - 12}
            </span>
          )}
        </div>
      )}

      {/* Center: edge legend (compact) */}
      {edgeLabels.length > 0 && (
        <div className="flex items-center gap-1.5 shrink-0">
          {edgeLabels.slice(0, 6).map(label => {
            const c = EDGE_LABEL_COLORS[label.toUpperCase()] ?? '#6b7280';
            return (
              <span
                key={label}
                className={`flex items-center gap-1 px-1.5 py-0.5 rounded ${FONT.caption}`}
                style={{ color: c, opacity: 0.7 }}
              >
                <span className="w-3 h-0.5 shrink-0" style={{ background: c }} />
                {label}
              </span>
            );
          })}
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
