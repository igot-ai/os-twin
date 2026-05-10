/**
 * useNexusExplorer — unified hook for the Nexus immersive knowledge explorer.
 *
 * Merges the graph explorer (seed/expand/search/path) with the RAG query
 * engine into a single state machine. Adds an exploration trail that
 * records every action the user takes.
 *
 * Endpoints consumed:
 * - GET  /knowledge/namespaces/{ns}/explorer/summary
 * - GET  /knowledge/namespaces/{ns}/explorer/seed
 * - POST /knowledge/namespaces/{ns}/explorer/expand
 * - POST /knowledge/namespaces/{ns}/explorer/search
 * - POST /knowledge/namespaces/{ns}/explorer/path
 * - GET  /knowledge/namespaces/{ns}/explorer/node/{id}
 * - POST /knowledge/namespaces/{ns}/query
 */

import { useState, useCallback, useRef } from 'react';
import { apiGet, apiPost } from '@/lib/api-client';
import type { QueryResultResponse } from '@/hooks/use-knowledge-query';
import type {
  ExplorerNode,
  ExplorerEdge,
  ExplorerGraphData,
  ExplorerPathData,
  ExplorerSummary,
  ExplorerNodeDetail,
  LensMode,
} from '@/hooks/use-knowledge-explorer';

// ---------------------------------------------------------------------------
// Trail types
// ---------------------------------------------------------------------------

export type TrailAction =
  | { type: 'seed'; topK: number }
  | { type: 'query'; query: string; mode: string }
  | { type: 'expand'; nodeId: string; depth: number }
  | { type: 'search'; query: string }
  | { type: 'path'; source: string; target: string }
  | { type: 'select'; nodeId: string };

export interface TrailEntry {
  id: string;
  action: TrailAction;
  timestamp: number;
  resultNodeCount: number;
  resultEdgeCount: number;
}

// ---------------------------------------------------------------------------
// Query mode
// ---------------------------------------------------------------------------

export type QueryMode = 'raw' | 'graph' | 'summarized';

// ---------------------------------------------------------------------------
// Path result
// ---------------------------------------------------------------------------

export interface PathResult {
  source: string;
  target: string;
  path: string[];
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

const KB = '/knowledge';

export function useNexusExplorer(namespace: string | null) {
  // ---- Accumulated graph ----
  const [nodesMap, setNodesMap] = useState<Map<string, ExplorerNode>>(new Map());
  const [edgesMap, setEdgesMap] = useState<Map<string, ExplorerEdge>>(new Map());

  // ---- Exploration state ----
  const [activeIgnitionPoints, setActiveIgnitionPoints] = useState<string[]>([]);
  const [selectedPath, setSelectedPath] = useState<PathResult | null>(null);
  const [activeLens, setActiveLens] = useState<LensMode>('structural');
  const [expansionDepth, setExpansionDepth] = useState(1);

  // ---- Selection ----
  const [selectedNode, setSelectedNode] = useState<ExplorerNode | null>(null);

  // ---- Query state ----
  const [queryResult, setQueryResult] = useState<QueryResultResponse | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<Error | null>(null);

  // ---- Trail ----
  const [trail, setTrail] = useState<TrailEntry[]>([]);

  // ---- Summary ----
  const [summary, setSummary] = useState<ExplorerSummary | null>(null);

  // ---- Brightness ----
  const [nodeBrightness, setNodeBrightness] = useState<Map<string, number>>(new Map());

  // ---- Loading flags ----
  const [isSeeding, setIsSeeding] = useState(false);
  const [isExpanding, setIsExpanding] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [isFindingPath, setIsFindingPath] = useState(false);

  const seedLoadedRef = useRef(false);
  let trailCounter = 0;

  // ---- Helper: merge graph data ----
  const mergeGraphData = useCallback((data: ExplorerGraphData) => {
    setNodesMap(prev => {
      const next = new Map(prev);
      for (const node of data.nodes) {
        next.set(node.id, node);
      }
      return next;
    });
    setEdgesMap(prev => {
      const next = new Map(prev);
      for (const edge of data.edges) {
        next.set(`${edge.source}->${edge.target}`, edge);
      }
      return next;
    });
  }, []);

  // ---- Helper: add trail entry ----
  const addTrail = useCallback((action: TrailAction, nodeCount: number, edgeCount: number) => {
    setTrail(prev => [
      {
        id: `trail-${Date.now()}-${++trailCounter}`,
        action,
        timestamp: Date.now(),
        resultNodeCount: nodeCount,
        resultEdgeCount: edgeCount,
      },
      ...prev,
    ]);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Helper: compute brightness ----
  const computeBrightness = useCallback(
    (ignitionPoints: string[], allNodes: Map<string, ExplorerNode>, allEdges: Map<string, ExplorerEdge>) => {
      const brightness = new Map<string, number>();
      for (const [id] of allNodes) brightness.set(id, 0.25);
      for (const id of ignitionPoints) brightness.set(id, 1.0);
      for (const [, edge] of allEdges) {
        if (ignitionPoints.includes(edge.source)) {
          brightness.set(edge.target, Math.max(brightness.get(edge.target) ?? 0.25, 0.65));
        }
        if (ignitionPoints.includes(edge.target)) {
          brightness.set(edge.source, Math.max(brightness.get(edge.source) ?? 0.25, 0.65));
        }
      }
      setNodeBrightness(brightness);
    },
    [],
  );

  // ---- Action: fetch summary ----
  const fetchSummary = useCallback(async () => {
    if (!namespace) return;
    try {
      const data = await apiGet<ExplorerSummary>(
        `${KB}/namespaces/${namespace}/explorer/summary`,
      );
      setSummary(data);
    } catch (err) {
      console.error('Nexus summary failed:', err);
    }
  }, [namespace]);

  // ---- Action: seed ----
  const seed = useCallback(async (topK = 50) => {
    if (!namespace) return;
    setIsSeeding(true);
    try {
      const data = await apiGet<ExplorerGraphData>(
        `${KB}/namespaces/${namespace}/explorer/seed?top_k=${topK}`,
      );
      mergeGraphData(data);

      const seedIds = data.nodes.slice(0, data.stats.seed_count ?? topK).map(n => n.id);
      setActiveIgnitionPoints(seedIds);

      const tmpNodes = new Map(data.nodes.map(n => [n.id, n]));
      const tmpEdges = new Map(data.edges.map(e => [`${e.source}->${e.target}`, e]));
      computeBrightness(seedIds, tmpNodes, tmpEdges);

      seedLoadedRef.current = true;
      addTrail({ type: 'seed', topK }, data.nodes.length, data.edges.length);

      await fetchSummary();
    } catch (err) {
      console.error('Nexus seed failed:', err);
    } finally {
      setIsSeeding(false);
    }
  }, [namespace, mergeGraphData, computeBrightness, addTrail, fetchSummary]);

  // ---- Action: expand (ignite) ----
  const expand = useCallback(async (nodeId: string, depth?: number) => {
    if (!namespace) return;
    setIsExpanding(true);
    try {
      const data = await apiPost<ExplorerGraphData>(
        `${KB}/namespaces/${namespace}/explorer/expand`,
        { node_ids: [nodeId], depth: depth ?? expansionDepth },
      );
      mergeGraphData(data);

      const newIgnition = [...new Set([...activeIgnitionPoints, nodeId])];
      setActiveIgnitionPoints(newIgnition);

      setNodesMap(cn => {
        setEdgesMap(ce => {
          computeBrightness(newIgnition, cn, ce);
          return ce;
        });
        return cn;
      });

      addTrail({ type: 'expand', nodeId, depth: depth ?? expansionDepth }, data.nodes.length, data.edges.length);
    } catch (err) {
      console.error('Nexus expand failed:', err);
    } finally {
      setIsExpanding(false);
    }
  }, [namespace, expansionDepth, activeIgnitionPoints, mergeGraphData, computeBrightness, addTrail]);

  // ---- Action: graph search ----
  const graphSearch = useCallback(async (query: string, limit = 20) => {
    if (!namespace || !query.trim()) return;
    setIsSearching(true);
    try {
      const data = await apiPost<ExplorerGraphData>(
        `${KB}/namespaces/${namespace}/explorer/search`,
        { query: query.trim(), limit },
      );
      mergeGraphData(data);

      const hitIds = data.nodes.map(n => n.id);
      const newIgnition = [...new Set([...activeIgnitionPoints, ...hitIds])];
      setActiveIgnitionPoints(newIgnition);

      setNodesMap(cn => {
        setEdgesMap(ce => {
          computeBrightness(newIgnition, cn, ce);
          return ce;
        });
        return cn;
      });

      addTrail({ type: 'search', query }, data.nodes.length, data.edges.length);
    } catch (err) {
      console.error('Nexus graph search failed:', err);
    } finally {
      setIsSearching(false);
    }
  }, [namespace, activeIgnitionPoints, mergeGraphData, computeBrightness, addTrail]);

  // ---- Action: RAG query (unified) ----
  const query = useCallback(async (q: string, mode: QueryMode = 'graph', topK = 10) => {
    if (!namespace || !q.trim()) return;
    setQueryLoading(true);
    setQueryError(null);
    try {
      const response = await apiPost<QueryResultResponse>(
        `${KB}/namespaces/${namespace}/query`,
        { query: q.trim(), mode, top_k: topK, threshold: 0.5 },
      );
      setQueryResult(response);

      // Also search the graph for the same query
      if (seedLoadedRef.current) {
        await graphSearch(q.trim(), topK);
      }

      addTrail({ type: 'query', query: q.trim(), mode }, 0, 0);
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setQueryError(error);
    } finally {
      setQueryLoading(false);
    }
  }, [namespace, graphSearch, addTrail]);

  // ---- Action: find path ----
  const tracePath = useCallback(async (sourceId: string, targetId: string) => {
    if (!namespace) return;
    setIsFindingPath(true);
    try {
      const data = await apiPost<ExplorerPathData>(
        `${KB}/namespaces/${namespace}/explorer/path`,
        { source_id: sourceId, target_id: targetId },
      );
      mergeGraphData(data);
      setSelectedPath({ source: sourceId, target: targetId, path: data.path });
      addTrail({ type: 'path', source: sourceId, target: targetId }, data.nodes.length, data.edges.length);
    } catch (err) {
      console.error('Nexus path failed:', err);
      setSelectedPath(null);
    } finally {
      setIsFindingPath(false);
    }
  }, [namespace, mergeGraphData, addTrail]);

  // ---- Action: select node ----
  const selectNode = useCallback((node: ExplorerNode | null) => {
    setSelectedNode(node);
    if (node) {
      addTrail({ type: 'select', nodeId: node.id }, 0, 0);
    }
  }, [addTrail]);

  // ---- Action: clear path ----
  const clearPath = useCallback(() => setSelectedPath(null), []);

  // ---- Action: clear query ----
  const clearQuery = useCallback(() => {
    setQueryResult(null);
    setQueryError(null);
  }, []);

  // ---- Action: get node detail ----
  const getNodeDetail = useCallback(async (nodeId: string): Promise<ExplorerNodeDetail | null> => {
    if (!namespace) return null;
    try {
      return await apiGet<ExplorerNodeDetail>(
        `${KB}/namespaces/${namespace}/explorer/node/${encodeURIComponent(nodeId)}`,
      );
    } catch (err) {
      console.error('Nexus node detail failed:', err);
      return null;
    }
  }, [namespace]);

  // ---- Action: reset ----
  const reset = useCallback(() => {
    setNodesMap(new Map());
    setEdgesMap(new Map());
    setActiveIgnitionPoints([]);
    setSelectedPath(null);
    setNodeBrightness(new Map());
    setSelectedNode(null);
    setQueryResult(null);
    setQueryError(null);
    setTrail([]);
    setSummary(null);
    seedLoadedRef.current = false;
  }, []);

  // ---- Derived ----
  const nodes = Array.from(nodesMap.values());
  const edges = Array.from(edgesMap.values());

  return {
    // Graph data
    nodes,
    edges,
    stats: { node_count: nodes.length, edge_count: edges.length },
    summary,

    // Exploration
    activeIgnitionPoints,
    selectedPath,
    activeLens,
    expansionDepth,
    nodeBrightness,
    isSeeded: seedLoadedRef.current,

    // Selection
    selectedNode,

    // Query
    queryResult,
    queryLoading,
    queryError,

    // Trail
    trail,

    // Loading
    isSeeding,
    isExpanding,
    isSearching,
    isFindingPath,
    isLoading: isSeeding || isExpanding || isSearching || isFindingPath,

    // Actions
    seed,
    expand,
    graphSearch,
    query,
    tracePath,
    selectNode,
    clearPath,
    clearQuery,
    getNodeDetail,
    fetchSummary,
    reset,
    setLens: setActiveLens,
    setDepth: setExpansionDepth,
  };
}
