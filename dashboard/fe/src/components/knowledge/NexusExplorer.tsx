'use client';

import React, { useCallback } from 'react';
import type { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';
import type { EntityHitResponse } from '@/hooks/use-knowledge-query';
import { useNexusExplorer } from '@/hooks/use-nexus-explorer';
import EmptyState from './nexus/EmptyState';
import { NexusProvider } from './nexus/NexusContext';
import NexusShell from './nexus/NexusShell';

interface NexusExplorerProps {
  namespaces: NamespaceMetaResponse[];
  selectedNamespace: string | null;
  onSelectNamespace: (ns: string) => void;
  onNoteClick?: (noteId: string) => void;
}

export default function NexusExplorer({
  namespaces,
  selectedNamespace,
  onSelectNamespace,
  onNoteClick,
}: NexusExplorerProps) {
  const nexus = useNexusExplorer(selectedNamespace, { autoSeed: true, autoSeedTopK: 50 });

  const handleEntityClick = useCallback(async (entity: EntityHitResponse) => {
    if (!selectedNamespace) return;
    await nexus.graphSearch(entity.name, 5);
    const found = nexus.nodes.find(n => n.id === entity.id || n.name === entity.name);
    if (found) {
      nexus.selectNode(found);
    }
  }, [selectedNamespace, nexus]);

  const handleConfirmPath = useCallback(async (sourceId: string, targetId: string) => {
    await nexus.tracePath(sourceId, targetId);
  }, [nexus]);

  if (!selectedNamespace) {
    return (
      <div className="h-full w-full relative overflow-hidden" style={{ background: 'var(--color-background)' }}>
        <EmptyState
          namespaces={namespaces}
          onSelectNamespace={onSelectNamespace}
        />
      </div>
    );
  }

  return (
    <NexusProvider
      namespaces={namespaces}
      selectedNamespace={selectedNamespace}
      onNamespaceChange={onSelectNamespace}
      nexusHook={nexus}
      queryMode={nexus.queryMode}
      setQueryMode={nexus.setQueryMode}
      onEntityClick={handleEntityClick}
      onNoteClick={onNoteClick}
      onConfirmPath={handleConfirmPath}
    >
      <NexusShell />
    </NexusProvider>
  );
}
