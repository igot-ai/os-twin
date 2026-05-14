'use client';

import React, { useMemo, useState, useRef, useEffect } from 'react';
import { useNexusContext } from './NexusContext';
import { getNodeColor, EDGE_LABEL_COLORS } from '../constants';
import { FONT } from './typography';
import { Icon } from './Icon';

export default function BottomRail() {
  const ctx = useNexusContext();
  const { graph, actions } = ctx;

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
