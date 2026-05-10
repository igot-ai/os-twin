'use client';

import React, { useCallback } from 'react';
import type { ExplorerNode } from '@/hooks/use-knowledge-explorer';

interface ActionBarProps {
  isLoading: boolean;
  isSeeded: boolean;
  selectedNode: ExplorerNode | null;
  expansionDepth: number;
  nodeCount: number;
  edgeCount: number;
  ignitionCount: number;
  hasPath: boolean;
  pathMode: boolean;
  onSeed: (topK?: number) => Promise<void>;
  onExpand: (nodeId: string) => Promise<void>;
  onTracePath: () => void;
  onReset: () => void;
  onClearPath: () => void;
  onSetDepth: (d: number) => void;
}

export default function ActionBar({
  isLoading,
  isSeeded,
  selectedNode,
  expansionDepth,
  nodeCount,
  edgeCount,
  ignitionCount,
  hasPath,
  pathMode,
  onSeed,
  onExpand,
  onTracePath,
  onReset,
  onClearPath,
  onSetDepth,
}: ActionBarProps) {
  const handleExpand = useCallback(() => {
    if (selectedNode) onExpand(selectedNode.id);
  }, [selectedNode, onExpand]);

  const handlePathClick = useCallback(() => {
    if (pathMode) {
      onTracePath();
      return;
    }
    onTracePath();
  }, [pathMode, onTracePath]);

  return (
    <div
      className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 rounded-xl border shadow-2xl max-w-[420px]"
      style={{
        background: 'rgba(255, 255, 255, 0.92)',
        borderColor: 'var(--color-border)',
        backdropFilter: 'blur(16px)',
      }}
    >
      {/* Main actions row */}
      <div className="flex items-center gap-2 px-3 py-2">
        {!isSeeded ? (
          <button
            onClick={() => onSeed(50)}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold text-white transition-all disabled:opacity-50"
            style={{ background: 'var(--color-primary)' }}
          >
            <span className="material-symbols-outlined text-[16px]">
              {isLoading ? 'progress_activity' : 'explore'}
            </span>
            {isLoading ? 'Loading...' : 'Sonar Ping'}
          </button>
        ) : (
          <>
            <button
              onClick={onReset}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-white/5"
              style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }}
            >
              <span className="material-symbols-outlined text-[14px]">restart_alt</span>
              Reset
            </button>

            {selectedNode && (
              <button
                onClick={handleExpand}
                disabled={isLoading}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-white/5 disabled:opacity-50"
                style={{ borderColor: 'var(--color-primary)', color: 'var(--color-primary)' }}
              >
                <span className="material-symbols-outlined text-[14px]">bubble</span>
                Expand
                <span className="text-[9px] opacity-60">d{expansionDepth}</span>
              </button>
            )}

            {isSeeded && selectedNode && (
              <button
                onClick={handlePathClick}
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors hover:bg-white/5"
                style={
                  pathMode
                    ? { borderColor: '#fbbf24', color: '#fbbf24' }
                    : { borderColor: 'var(--color-border)', color: 'var(--color-text-muted)' }
                }
              >
                <span className="material-symbols-outlined text-[14px]">route</span>
                {pathMode ? 'Select Target...' : 'Trace Path'}
              </button>
            )}

            {hasPath && (
              <button
                onClick={onClearPath}
                className="flex items-center gap-1 px-2 py-1.5 rounded-lg text-[11px] font-medium transition-colors hover:bg-white/5"
                style={{ color: '#fbbf24' }}
              >
                <span className="material-symbols-outlined text-[14px]">close</span>
                Clear Path
              </button>
            )}
          </>
        )}

        <div className="ml-auto flex items-center gap-3 text-[9px]" style={{ color: 'var(--color-text-muted)' }}>
          {isSeeded && nodeCount > 0 && (
            <>
              <span>{nodeCount} nodes</span>
              <span>{edgeCount} edges</span>
              {ignitionCount > 0 && (
                <span style={{ color: 'var(--color-primary)' }}>{ignitionCount} ignited</span>
              )}
            </>
          )}
        </div>
      </div>

      {/* Path mode hint */}
      {pathMode && (
        <div
          className="px-3 py-1.5 border-t text-[10px] text-center"
          style={{ borderColor: 'var(--color-border)', color: '#fbbf24' }}
        >
          Click a target node to trace the path from &quot;{selectedNode?.name}&quot;
        </div>
      )}
    </div>
  );
}
