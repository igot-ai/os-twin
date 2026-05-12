'use client';

import React from 'react';
import { useNexusContext } from './NexusContext';
import ResultsDrawer from './ResultsDrawer';
import ExplorationTrail from './ExplorationTrail';
import { FONT } from './typography';
import { Icon } from './Icon';

export default function LeftDock({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const ctx = useNexusContext();
  const { query, trail, actions } = ctx;

  const [resultsCollapsed, setResultsCollapsed] = React.useState(false);

  if (collapsed) {
    return (
      <div
        className="flex flex-col items-center py-2 border-r"
        style={{ width: 32, borderColor: 'var(--color-border)', background: 'var(--surface-overlay-bg)' }}
      >
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-white/10 transition-colors"
          title="Expand left dock"
        >
          <Icon name="chevron_right" size={14} style={{ color: 'var(--color-text-muted)' }} />
        </button>
        {query.queryResult && (
          <span className={`${FONT.caption} mt-2`} style={{ color: 'var(--color-primary)' }}>
            {query.queryResult.chunks.length}
          </span>
        )}
      </div>
    );
  }

  return (
    <div
      className="overflow-hidden flex flex-col border-r"
      style={{ width: 320, borderColor: 'var(--color-border)', background: 'var(--surface-overlay-bg)' }}
    >
      <div className="flex items-center justify-between px-2 py-1 border-b shrink-0" style={{ borderColor: 'var(--color-border)' }}>
        <span className={`${FONT.label} font-semibold uppercase tracking-wide`} style={{ color: 'var(--color-text-muted)' }}>
          Explore
        </span>
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-white/10 transition-colors"
          title="Collapse left dock"
        >
          <Icon name="chevron_left" size={14} style={{ color: 'var(--color-text-muted)' }} />
        </button>
      </div>
      <div className="flex-1 overflow-hidden flex flex-col">
        <ResultsDrawer
          result={query.queryResult}
          mode={query.queryMode}
          isCollapsed={resultsCollapsed}
          onToggle={() => setResultsCollapsed(!resultsCollapsed)}
          onEntityClick={actions.onEntityClick}
          onNoteClick={actions.onNoteClick}
          docked
        />
        <div className="mt-auto p-2">
          <ExplorationTrail trail={trail.trail} docked />
        </div>
      </div>
    </div>
  );
}
