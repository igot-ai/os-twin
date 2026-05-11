'use client';

import React, { useRef, useCallback, useMemo, useState, useEffect } from 'react';
import { useNexusContext } from './NexusContext';
import NexusCanvas from './NexusCanvas';
import TopRail from './TopRail';
import BottomRail from './BottomRail';
import LeftDock from './LeftDock';
import RightDock from './RightDock';
import Minimap from './Minimap';
import { useDockState } from './useDockState';
import { useShortcuts } from './useShortcuts';
import { Icon } from './Icon';

export default function NexusShell() {
  const ctx = useNexusContext();
  const { graph, query, actions, path } = ctx;
  const leftDock = useDockState('left');
  const rightDock = useDockState('right');
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (graph.selectedNode && rightDock.collapsed) {
      rightDock.toggle();
    }
  }, [graph.selectedNode]);

  const visibleError = useMemo(() => {
    if (!query.queryError || dismissed) return null;
    return query.queryError.message;
  }, [query.queryError, dismissed]);

  const focusSearch = useCallback(() => {
    searchInputRef.current?.focus();
  }, []);

  useShortcuts({
    onFocusSearch: focusSearch,
    onClearSelection: () => path.handleNodeClick(null),
    onReset: actions.reset,
    onSetLens: actions.setLens,
    onToggleLeftDock: leftDock.toggle,
    onToggleRightDock: rightDock.toggle,
  });

  const leftWidth = leftDock.collapsed ? 32 : 320;
  const rightWidth = rightDock.collapsed || !graph.selectedNode ? 32 : 360;

  return (
    <div
      className="h-full w-full"
      style={{
        display: 'grid',
        gridTemplateRows: '44px 1fr 36px',
        gridTemplateColumns: `${leftWidth}px 1fr ${rightWidth}px`,
        background: 'var(--color-background)',
        transition: 'grid-template-columns 0.2s ease',
      }}
    >
      <TopRail searchInputRef={searchInputRef} />

      <LeftDock collapsed={leftDock.collapsed} onToggle={leftDock.toggle} />

      {/* Canvas — center cell */}
      <div className="relative overflow-hidden" style={{ isolation: 'isolate' }}>
        <NexusCanvas
          nodes={graph.nodes}
          edges={graph.edges}
          isLoading={graph.isLoading}
          selectedNode={graph.selectedNode}
          onSelectNode={path.handleNodeClick}
          onIgnite={actions.expand}
          nodeBrightness={graph.nodeBrightness}
          activeIgnitionPoints={graph.activeIgnitionPoints}
          selectedPath={graph.selectedPath}
          highlightedLabels={graph.highlightedLabels}
          communityLens={graph.activeLens === 'community'}
        />
        {/* Overlay layer — sits above canvas */}
        <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 1 }}>
          {!graph.selectedNode && graph.isSeeded && (
            <div className="absolute bottom-2 right-2 pointer-events-auto">
              <Minimap
                nodes={graph.nodes}
                edges={graph.edges}
                selectedNodeId={null}
                ignitionPoints={graph.activeIgnitionPoints}
                docked
              />
            </div>
          )}
          {visibleError && (
            <div
              className="absolute top-2 left-1/2 -translate-x-1/2 pointer-events-auto px-3 py-2 rounded-lg text-xs flex items-center gap-2 shadow-lg"
              style={{ background: 'rgba(239, 68, 68, 0.08)', color: '#ef4444' }}
            >
              <Icon name="error" size={16} />
              {visibleError}
              <button
                onClick={() => setDismissed(true)}
                className="ml-1 p-0.5 rounded hover:bg-white/10"
              >
                <Icon name="close" size={12} style={{ color: '#ef4444' }} />
              </button>
            </div>
          )}
          {path.pathSource && (
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-auto px-4 py-2 rounded-xl border shadow-2xl text-xs font-medium"
              style={{
                background: 'var(--surface-overlay-bg)',
                borderColor: 'rgba(251, 191, 36, 0.4)',
                color: '#fbbf24',
                backdropFilter: 'var(--surface-overlay-blur)',
              }}
            >
              <Icon name="route" size={14} className="align-middle mr-1" />
              Click a target node to trace path
              <button
                onClick={() => path.setPathSource(null)}
                className="ml-2 p-0.5 rounded hover:bg-white/10"
              >
                <Icon name="close" size={12} />
              </button>
            </div>
          )}
        </div>
      </div>

      <RightDock collapsed={rightDock.collapsed} onToggle={rightDock.toggle} />

      <BottomRail />
    </div>
  );
}
