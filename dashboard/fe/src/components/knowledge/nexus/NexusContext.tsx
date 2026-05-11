'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import type { ExplorerNode, ExplorerEdge, LensMode } from '@/hooks/use-knowledge-explorer';
import type { QueryResultResponse, EntityHitResponse } from '@/hooks/use-knowledge-query';
import type { TrailEntry, QueryMode } from '@/hooks/use-nexus-explorer';
import type { NamespaceMetaResponse } from '@/hooks/use-knowledge-namespaces';

export interface NexusContextValue {
  namespace: {
    namespaces: NamespaceMetaResponse[];
    selectedNamespace: string | null;
    onNamespaceChange: (ns: string) => void;
  };
  graph: {
    nodes: ExplorerNode[];
    edges: ExplorerEdge[];
    selectedNode: ExplorerNode | null;
    activeLens: LensMode;
    expansionDepth: number;
    activeIgnitionPoints: string[];
    selectedPath: { source: string; target: string; path: string[] } | null;
    nodeBrightness: Map<string, number>;
    isLoading: boolean;
    isSeeded: boolean;
    highlightedLabels: Set<string>;
    setHighlightedLabels: React.Dispatch<React.SetStateAction<Set<string>>>;
  };
  query: {
    queryResult: QueryResultResponse | null;
    queryLoading: boolean;
    queryError: Error | null;
    queryMode: QueryMode;
    setQueryMode: (mode: QueryMode) => void;
  };
  trail: {
    trail: TrailEntry[];
  };
  actions: {
    seed: (topK?: number) => Promise<void>;
    expand: (nodeId: string) => Promise<void>;
    graphSearch: (query: string, limit?: number) => Promise<void>;
    query: (q: string, mode: QueryMode, topK: number) => Promise<void>;
    tracePath: (sourceId: string, targetId: string) => Promise<void>;
    selectNode: (node: ExplorerNode | null) => void;
    reset: () => void;
    clearPath: () => void;
    clearQuery: () => void;
    setLens: (lens: LensMode) => void;
    setDepth: (d: number) => void;
    onEntityClick: (entity: EntityHitResponse) => void;
    onNoteClick?: (noteId: string) => void;
  };
  path: {
    pathSource: string | null;
    setPathSource: (id: string | null) => void;
    pathMode: boolean;
    togglePathMode: () => void;
    tracePathFromCard: (sourceId: string) => void;
    handleNodeClick: (node: ExplorerNode | null) => void;
  };
}

const NexusContext = createContext<NexusContextValue | null>(null);

export function useNexusContext(): NexusContextValue {
  const ctx = useContext(NexusContext);
  if (!ctx) throw new Error('useNexusContext must be used inside <NexusProvider>');
  return ctx;
}

interface NexusProviderProps {
  children: React.ReactNode;
  namespaces: NamespaceMetaResponse[];
  selectedNamespace: string | null;
  onNamespaceChange: (ns: string) => void;
  nexusHook: ReturnType<typeof import('@/hooks/use-nexus-explorer').useNexusExplorer>;
  queryMode: QueryMode;
  setQueryMode: (mode: QueryMode) => void;
  onEntityClick: (entity: EntityHitResponse) => void;
  onNoteClick?: (noteId: string) => void;
  onConfirmPath: (sourceId: string, targetId: string) => Promise<void>;
}

export function NexusProvider({
  children,
  namespaces,
  selectedNamespace,
  onNamespaceChange,
  nexusHook,
  queryMode,
  setQueryMode,
  onEntityClick,
  onNoteClick,
  onConfirmPath,
}: NexusProviderProps) {
  const [pathSource, setPathSource] = useState<string | null>(null);
  const [highlightedLabels, setHighlightedLabels] = useState<Set<string>>(new Set());

  const pathMode = pathSource !== null;

  const togglePathMode = useCallback(() => {
    if (pathSource) {
      setPathSource(null);
    } else if (nexusHook.selectedNode) {
      setPathSource(nexusHook.selectedNode.id);
    }
  }, [pathSource, nexusHook.selectedNode]);

  const tracePathFromCard = useCallback((sourceId: string) => {
    setPathSource(sourceId);
  }, []);

  const handleNodeClick = useCallback((node: ExplorerNode | null) => {
    if (pathSource && node) {
      onConfirmPath(pathSource, node.id);
      setPathSource(null);
      return;
    }
    nexusHook.selectNode(node);
  }, [pathSource, onConfirmPath, nexusHook]);

  const value: NexusContextValue = {
    namespace: {
      namespaces,
      selectedNamespace,
      onNamespaceChange,
    },
    graph: {
      nodes: nexusHook.nodes,
      edges: nexusHook.edges,
      selectedNode: nexusHook.selectedNode,
      activeLens: nexusHook.activeLens,
      expansionDepth: nexusHook.expansionDepth,
      activeIgnitionPoints: nexusHook.activeIgnitionPoints,
      selectedPath: nexusHook.selectedPath,
      nodeBrightness: nexusHook.nodeBrightness,
      isLoading: nexusHook.isLoading,
      isSeeded: nexusHook.isSeeded,
      highlightedLabels,
      setHighlightedLabels,
    },
    query: {
      queryResult: nexusHook.queryResult,
      queryLoading: nexusHook.queryLoading,
      queryError: nexusHook.queryError,
      queryMode,
      setQueryMode,
    },
    trail: {
      trail: nexusHook.trail,
    },
    actions: {
      seed: nexusHook.seed,
      expand: nexusHook.expand,
      graphSearch: nexusHook.graphSearch,
      query: nexusHook.query,
      tracePath: nexusHook.tracePath,
      selectNode: nexusHook.selectNode,
      reset: nexusHook.reset,
      clearPath: nexusHook.clearPath,
      clearQuery: nexusHook.clearQuery,
      setLens: nexusHook.setLens,
      setDepth: nexusHook.setDepth,
      onEntityClick,
      onNoteClick,
    },
    path: {
      pathSource,
      setPathSource,
      pathMode,
      togglePathMode,
      tracePathFromCard,
      handleNodeClick,
    },
  };

  return (
    <NexusContext.Provider value={value}>
      {children}
    </NexusContext.Provider>
  );
}
