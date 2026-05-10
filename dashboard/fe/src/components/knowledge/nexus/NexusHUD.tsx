'use client';

import React from 'react';
import type { ExplorerNode, ExplorerEdge, LensMode } from '@/hooks/use-knowledge-explorer';
import type { QueryResultResponse, EntityHitResponse } from '@/hooks/use-knowledge-query';
import type { TrailEntry, QueryMode } from '@/hooks/use-nexus-explorer';
import NamespaceSwitcher from './NamespaceSwitcher';
import LensSelector from './LensSelector';
import SearchBar from './SearchBar';
import ResultsDrawer from './ResultsDrawer';
import ContextualCard from './ContextualCard';
import ActionBar from './ActionBar';
import ExplorationTrail from './ExplorationTrail';
import Minimap from './Minimap';
import type { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';

interface NexusHUDProps {
  namespaces: NamespaceMetaResponse[];
  selectedNamespace: string | null;
  onNamespaceChange: (ns: string) => void;
  nodes: ExplorerNode[];
  edges: ExplorerEdge[];
  selectedNode: ExplorerNode | null;
  activeLens: LensMode;
  expansionDepth: number;
  activeIgnitionPoints: string[];
  selectedPath: { source: string; target: string; path: string[] } | null;
  isLoading: boolean;
  isSeeded: boolean;
  queryResult: QueryResultResponse | null;
  queryLoading: boolean;
  queryError: Error | null;
  queryMode: string;
  trail: TrailEntry[];
  onSeed: (topK?: number) => Promise<void>;
  onExpand: (nodeId: string) => Promise<void>;
  onQuery: (q: string, mode: QueryMode, topK: number) => Promise<void>;
  onConfirmPath: (sourceId: string, targetId: string) => Promise<void>;
  onSelectNode: (node: ExplorerNode | null) => void;
  onReset: () => void;
  onClearPath: () => void;
  onClearQuery: () => void;
  onSetLens: (lens: LensMode) => void;
  onSetDepth: (d: number) => void;
  onEntityClick: (entity: EntityHitResponse) => void;
  onNoteClick?: (noteId: string) => void;
}

export default function NexusHUD({
  namespaces,
  selectedNamespace,
  onNamespaceChange,
  nodes,
  edges,
  selectedNode,
  activeLens,
  expansionDepth,
  activeIgnitionPoints,
  selectedPath,
  isLoading,
  isSeeded,
  queryResult,
  queryLoading,
  queryError,
  queryMode,
  trail,
  onSeed,
  onExpand,
  onQuery,
  onConfirmPath,
  onSelectNode,
  onReset,
  onClearPath,
  onClearQuery,
  onSetLens,
  onSetDepth,
  onEntityClick,
  onNoteClick,
}: NexusHUDProps) {
  const [resultsCollapsed, setResultsCollapsed] = React.useState(false);
  const [pathSource, setPathSource] = React.useState<string | null>(null);

  const pathMode = pathSource !== null;

  const handleTogglePathMode = React.useCallback(() => {
    if (pathSource) {
      setPathSource(null);
    } else if (selectedNode) {
      setPathSource(selectedNode.id);
    }
  }, [pathSource, selectedNode]);

  const handleTracePathFromCard = React.useCallback((sourceId: string) => {
    setPathSource(sourceId);
  }, []);

  const handleNodeClick = React.useCallback((node: ExplorerNode | null) => {
    if (pathSource && node) {
      onConfirmPath(pathSource, node.id);
      setPathSource(null);
      return;
    }
    onSelectNode(node);
  }, [pathSource, onConfirmPath, onSelectNode]);

  return (
    <div className="absolute inset-0 z-10 pointer-events-none">
      {/* Top bar */}
      <div
        className="absolute top-0 left-0 right-0 z-30 flex items-center justify-between px-3 py-2 pointer-events-auto"
        style={{
          background: 'linear-gradient(180deg, rgba(255,255,255,0.9) 0%, transparent 100%)',
        }}
      >
        <NamespaceSwitcher
          namespaces={namespaces}
          selected={selectedNamespace}
          onSelect={onNamespaceChange}
        />
        {isSeeded && <LensSelector active={activeLens} onSet={onSetLens} />}
      </div>

      {/* Search bar */}
      <div className="pointer-events-auto">
        <SearchBar
          isLoading={queryLoading}
          hasQuery={!!queryResult}
          onQuery={onQuery}
          onClear={onClearQuery}
        />
      </div>

      {/* Error toast */}
      {queryError && (
        <div
          className="absolute top-20 left-1/2 -translate-x-1/2 z-30 pointer-events-auto px-3 py-2 rounded-lg text-xs flex items-center gap-2 shadow-lg"
          style={{ background: 'rgba(239, 68, 68, 0.08)', color: '#ef4444' }}
        >
          <span className="material-symbols-outlined text-[16px]">error</span>
          {queryError.message}
        </div>
      )}

      {/* Results drawer */}
      <div className="pointer-events-auto">
        <ResultsDrawer
          result={queryResult}
          mode={queryMode}
          isCollapsed={resultsCollapsed}
          onToggle={() => setResultsCollapsed(!resultsCollapsed)}
          onEntityClick={onEntityClick}
          onNoteClick={onNoteClick}
        />
      </div>

      {/* Contextual card */}
      <div className="pointer-events-auto">
        <ContextualCard
          node={selectedNode}
          edges={edges}
          isLoading={isLoading}
          onExpand={onExpand}
          onTracePath={handleTracePathFromCard}
          onClose={() => handleNodeClick(null)}
        />
      </div>

      {/* Minimap (only when no selected node) */}
      {!selectedNode && isSeeded && (
        <div className="pointer-events-auto">
          <Minimap
            nodes={nodes}
            edges={edges}
            selectedNodeId={null}
            ignitionPoints={activeIgnitionPoints}
          />
        </div>
      )}

      {/* Exploration trail */}
      <div className="pointer-events-auto">
        <ExplorationTrail trail={trail} />
      </div>

      {/* Action bar */}
      <div className="pointer-events-auto">
        <ActionBar
          isLoading={isLoading}
          isSeeded={isSeeded}
          selectedNode={selectedNode}
          expansionDepth={expansionDepth}
          nodeCount={nodes.length}
          edgeCount={edges.length}
          ignitionCount={activeIgnitionPoints.length}
          hasPath={!!selectedPath}
          pathMode={pathMode}
          onSeed={onSeed}
          onExpand={onExpand}
          onTracePath={handleTogglePathMode}
          onReset={onReset}
          onClearPath={onClearPath}
          onSetDepth={onSetDepth}
        />
      </div>

      {/* Path source indicator */}
      {pathSource && (
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 pointer-events-auto px-4 py-2 rounded-xl border shadow-2xl text-xs font-medium"
          style={{
            background: 'rgba(255, 255, 255, 0.95)',
            borderColor: 'rgba(251, 191, 36, 0.4)',
            color: '#fbbf24',
            backdropFilter: 'blur(12px)',
          }}
        >
          <span className="material-symbols-outlined text-[14px] align-middle mr-1">route</span>
          Click a target node to trace path
          <button
            onClick={() => setPathSource(null)}
            className="ml-2 p-0.5 rounded hover:bg-white/10"
          >
            <span className="material-symbols-outlined text-[12px]">close</span>
          </button>
        </div>
      )}
    </div>
  );
}
