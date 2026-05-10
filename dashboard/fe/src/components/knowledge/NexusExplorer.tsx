'use client';

/**
 * NexusExplorer — immersive knowledge graph explorer.
 *
 * Layout:
 * ┌──────────────────────────────────────────────────────────────┐
 * │  [Namespace ▾]      NEXUS      [structural▾] [semantic] [cat] │
 * │──────────────────────────────────────────────────────────────│
 * │  ┌─── Search Bar (floating, top center) ───┐                │
 * │  │  [🔍 Explore knowledge...  ] [graph▾][K:10][→]  │        │
 * │  └─────────────────────────────────────────┘                │
 * │                                                              │
 * │ ┌─ Results ──┐          FULL GRAPH       ┌─ Node Detail ──┐ │
 * │ │ (drawer)   │         (NexusCanvas      │ (ContextualCard)│ │
 * │ │  Answer    │          WebGL)           │  Properties     │ │
 * │ │  Chunks    │                          │  [Expand][Path] │ │
 * │ │  Entities  │                          └─────────────────┘ │
 * │ └───────────┘                                               │
 * │                                                              │
 * │  seed → expand(2) → query("themes")  (ExplorationTrail)     │
 * │──────────────────────────────────────────────────────────────│
 * │  [◉ Sonar] [⊕ Expand] [⇢ Path] [⟲ Reset]  d:[1][2][3]    │
 * └──────────────────────────────────────────────────────────────┘
 */

import React, { useState, useCallback, useEffect } from 'react';
import type { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';
import type { EntityHitResponse } from '@/hooks/use-knowledge-query';
import type { QueryMode } from '@/hooks/use-nexus-explorer';
import { useNexusExplorer } from '@/hooks/use-nexus-explorer';
import NexusCanvas from './nexus/NexusCanvas';
import NexusHUD from './nexus/NexusHUD';
import EmptyState from './nexus/EmptyState';
import type { ExplorerNode } from '@/hooks/use-knowledge-explorer';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface NexusExplorerProps {
  namespaces: NamespaceMetaResponse[];
  selectedNamespace: string | null;
  onSelectNamespace: (ns: string) => void;
  onNoteClick?: (noteId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function NexusExplorer({
  namespaces,
  selectedNamespace,
  onSelectNamespace,
  onNoteClick,
}: NexusExplorerProps) {
  const nexus = useNexusExplorer(selectedNamespace);

  const [queryMode, setQueryMode] = useState<string>('graph');

  // Auto-seed when namespace changes
  useEffect(() => {
    if (selectedNamespace && !nexus.isSeeded) {
      nexus.seed(50);
    }
  }, [selectedNamespace]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-ignite query entities on graph
  const handleEntityClick = useCallback(async (entity: EntityHitResponse) => {
    if (!selectedNamespace) return;
    await nexus.graphSearch(entity.name, 5);
    const found = nexus.nodes.find(n => n.id === entity.id || n.name === entity.name);
    if (found) {
      nexus.selectNode(found);
    }
  }, [selectedNamespace, nexus]);

  // Handle query submit (from SearchBar)
  const handleQuery = useCallback(async (q: string, mode: QueryMode, topK: number) => {
    setQueryMode(mode);
    await nexus.query(q, mode, topK);
  }, [nexus]);

  // Handle node selection from canvas
  const handleSelectNode = useCallback((node: ExplorerNode | null) => {
    nexus.selectNode(node);
  }, [nexus]);

  // Handle path confirmation (source + target selected)
  const handleConfirmPath = useCallback(async (sourceId: string, targetId: string) => {
    await nexus.tracePath(sourceId, targetId);
  }, [nexus]);

  // Empty state
  if (!selectedNamespace) {
    return (
      <div className="h-full w-full relative overflow-hidden" style={{ background: 'var(--color-background)' }}>
        <EmptyState onSelectNamespace={() => {
          if (namespaces.length > 0) onSelectNamespace(namespaces[0].name);
        }} />
      </div>
    );
  }

  return (
    <div className="h-full w-full relative overflow-hidden" style={{ background: 'var(--color-background)' }}>
      {/* Layer 1: WebGL Graph Canvas */}
      <NexusCanvas
        nodes={nexus.nodes}
        edges={nexus.edges}
        isLoading={nexus.isLoading}
        selectedNode={nexus.selectedNode}
        onSelectNode={handleSelectNode}
        onIgnite={nexus.expand}
        nodeBrightness={nexus.nodeBrightness}
        activeIgnitionPoints={nexus.activeIgnitionPoints}
        selectedPath={nexus.selectedPath}
      />

      {/* Layer 2: HUD overlay */}
      <NexusHUD
        namespaces={namespaces}
        selectedNamespace={selectedNamespace}
        onNamespaceChange={onSelectNamespace}
        nodes={nexus.nodes}
        edges={nexus.edges}
        selectedNode={nexus.selectedNode}
        activeLens={nexus.activeLens}
        expansionDepth={nexus.expansionDepth}
        activeIgnitionPoints={nexus.activeIgnitionPoints}
        selectedPath={nexus.selectedPath}
        isLoading={nexus.isLoading}
        isSeeded={nexus.isSeeded}
        queryResult={nexus.queryResult}
        queryLoading={nexus.queryLoading}
        queryError={nexus.queryError}
        queryMode={queryMode}
        trail={nexus.trail}
        onSeed={nexus.seed}
        onExpand={nexus.expand}
        onQuery={handleQuery}
        onConfirmPath={handleConfirmPath}
        onSelectNode={handleSelectNode}
        onReset={nexus.reset}
        onClearPath={nexus.clearPath}
        onClearQuery={nexus.clearQuery}
        onSetLens={nexus.setLens}
        onSetDepth={nexus.setDepth}
        onEntityClick={handleEntityClick}
        onNoteClick={onNoteClick}
      />
    </div>
  );
}
